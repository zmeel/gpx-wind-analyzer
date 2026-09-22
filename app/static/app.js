let map = null;
let routeLayers = [];
let arrowDistance = 0;

// Must match FORECAST_FUTURE_LIMIT_DAYS in app/weather.py.
const FORECAST_FUTURE_LIMIT_DAYS = 16;

// ============================
// KAART INITIALISATIE
// ============================

document.addEventListener("DOMContentLoaded", function () {
  const mapElement = document.getElementById("map");
  if (!mapElement) {
    console.error("Map element niet gevonden");
    return;
  }
  if (!window.L) {
    console.error("Leaflet niet geladen");
    return;
  }

  map = L.map("map", { preferCanvas: true });
  map.setView([52.05, 5.15], 10);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "OpenStreetMap",
  }).addTo(map);

  setTimeout(() => map.invalidateSize(), 500);

  initDateField();
  setStatus("Kaart geladen.");
});

function initDateField() {
  const dateField = document.getElementById("rideDate");
  if (!dateField) return;

  const today = new Date();
  const maxDate = new Date(today);
  maxDate.setDate(maxDate.getDate() + FORECAST_FUTURE_LIMIT_DAYS);

  dateField.value = toISODate(today);
  dateField.max = toISODate(maxDate);
}

function toISODate(date) {
  return date.toISOString().slice(0, 10);
}

// ============================
// STATUS
// ============================

function setStatus(text) {
  const status = document.getElementById("status");
  if (status) status.innerHTML = text;
}

// ============================
// UPLOAD
// ============================

async function upload() {
  const file = document.getElementById("file").files[0];
  if (!file) {
    setStatus("Selecteer eerst een GPX bestand.");
    return;
  }

  const date = document.getElementById("rideDate").value;
  const time = document.getElementById("rideTime").value;
  if (!date || !time) {
    setStatus("Kies een datum en tijd voor de rit.");
    return;
  }

  const directionElement = document.getElementById("direction");
  const direction = directionElement ? directionElement.value : "normal";

  const formData = new FormData();
  formData.append("file", file);
  formData.append("date", date);
  formData.append("time", time);
  formData.append("direction", direction);

  setStatus("Bezig met analyseren...");

  try {
    const response = await fetch("/upload", { method: "POST", body: formData });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Server fout");
    }

    updateInfo(data);
    clearMap();
    drawRoute(data);
    setStatus("Analyse klaar.");
  } catch (error) {
    console.error(error);
    setStatus("Fout: " + error.message);
  }
}

// ============================
// INFO
// ============================

function updateInfo(data) {
  const route = data.route || data;

  const distanceElement = document.getElementById("distance");
  if (distanceElement && route.distance_km !== undefined) {
    distanceElement.innerHTML = Number(route.distance_km).toFixed(2) + " km";
  }

  const pointsElement = document.getElementById("points");
  if (pointsElement && route.points !== undefined) {
    pointsElement.innerHTML = Array.isArray(route.points) ? route.points.length : route.points;
  }

  const summary = data.wind && data.wind.summary;
  if (!summary) return;

  setText("headwind", summary.tegenwind_segmenten ?? "-");
  setText("tailwind", summary.meewind_segmenten ?? "-");
  setText("crosswind", summary.zijwind_segmenten ?? "-");

  const speedElement = document.getElementById("windspeed");
  if (speedElement) {
    speedElement.innerHTML =
      summary.gemiddelde_windsnelheid !== undefined ? summary.gemiddelde_windsnelheid + " km/u" : "-";
  }

  const directionElement = document.getElementById("winddirection");
  if (directionElement && summary.wind_direction !== undefined) {
    directionElement.innerHTML = degreesToCompass(Number(summary.wind_direction));
  }
}

function setText(elementId, value) {
  const element = document.getElementById(elementId);
  if (element) element.innerHTML = value;
}

// ============================
// ROUTE TEKENEN
// ============================

function drawRoute(data) {
  if (data.wind && data.wind.segments) {
    drawWindSegments(data.wind.segments);
    return;
  }

  const route = data.route || data;
  if (!route.coordinates) return;

  const line = L.polyline(route.coordinates, { color: "blue", weight: 5 }).addTo(map);
  routeLayers.push(line);
  map.fitBounds(line.getBounds());
}

const CLASSIFICATION_COLORS = {
  tegenwind: "red",
  meewind: "green",
};
const DEFAULT_SEGMENT_COLOR = "yellow";

function drawWindSegments(segments) {
  const bounds = L.latLngBounds();
  arrowDistance = 0;

  segments.forEach((segment) => {
    const color = CLASSIFICATION_COLORS[segment.classification] || DEFAULT_SEGMENT_COLOR;

    const line = L.polyline(segment.coordinates, { color, weight: 6 }).addTo(map);
    line.bindPopup(`
      <b>Segment ${segment.index}</b><br>
      Rijrichting: ${segment.bearing} deg<br>
      Wind: ${segment.wind_speed} km/u<br>
      Windrichting: ${segment.wind_direction} deg<br>
      Component: ${segment.component} km/u<br>
      <b>${segment.classification}</b>
    `);

    routeLayers.push(line);
    drawDirectionArrowEveryKm(segment);

    bounds.extend(segment.coordinates[0]);
    bounds.extend(segment.coordinates[1]);
  });

  map.fitBounds(bounds);
}

// ============================
// 1 PIJL PER KM
// ============================

function drawDirectionArrowEveryKm(segment) {
  const start = segment.coordinates[0];
  const end = segment.coordinates[1];

  const distance = L.latLng(start[0], start[1]).distanceTo(L.latLng(end[0], end[1]));
  arrowDistance += distance;
  if (arrowDistance < 1000) return;
  arrowDistance = 0;

  const midLat = (start[0] + end[0]) / 2;
  const midLon = (start[1] + end[1]) / 2;

  const shaftLength = 0.00035;
  const headLength = 0.00015;
  const headSpreadRad = 2.6;
  const angle = (segment.bearing * Math.PI) / 180;

  const tip = [midLat + Math.cos(angle) * shaftLength, midLon + Math.sin(angle) * shaftLength];
  const left = [tip[0] + Math.cos(angle + headSpreadRad) * headLength, tip[1] + Math.sin(angle + headSpreadRad) * headLength];
  const right = [tip[0] + Math.cos(angle - headSpreadRad) * headLength, tip[1] + Math.sin(angle - headSpreadRad) * headLength];

  const arrow = L.polyline([[midLat, midLon], tip, left, tip, right], { color: "black", weight: 3 }).addTo(map);
  routeLayers.push(arrow);
}

// ============================
// KAART OPSCHONEN
// ============================

function clearMap() {
  routeLayers.forEach((layer) => map.removeLayer(layer));
  routeLayers = [];
  arrowDistance = 0;
}

// ============================
// GRADEN NAAR WINDRICHTING
// ============================

function degreesToCompass(degrees) {
  const directions = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"];
  const index = Math.round(degrees / 45) % 8;
  return directions[index];
}
