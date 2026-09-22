let map = null;
let routeLayers = [];
let arrowDistance = 0;

// Must match FORECAST_FUTURE_LIMIT_DAYS in app/weather.py.
const FORECAST_FUTURE_LIMIT_DAYS = 16;

const CLASSIFICATION_COLORS = {
  tegenwind: "#e0433b",
  meewind: "#2fa860",
};
const DEFAULT_SEGMENT_COLOR = "#e8b93a";

// Route 1 is a solid line, route 2 (when present) is dashed, so overlapping
// routes stay distinguishable even though both use the same wind colors.
const ROUTE_DASH_ARRAYS = [null, "10, 8"];

// ============================
// KAART INITIALISATIE
// ============================

document.addEventListener("DOMContentLoaded", function () {
  // These don't depend on Leaflet, so wire them up even if the map fails to load.
  initDateField();
  initSecondRouteToggle();

  const mapElement = document.getElementById("map");
  if (!mapElement) {
    console.error("Map element niet gevonden");
    return;
  }
  if (!window.L) {
    console.error("Leaflet niet geladen");
    setStatus("Kaart kon niet geladen worden, maar analyseren werkt nog wel.");
    return;
  }

  map = L.map("map", { preferCanvas: true });
  map.setView([52.05, 5.15], 10);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "OpenStreetMap",
  }).addTo(map);

  setTimeout(() => map.invalidateSize(), 500);

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

function initSecondRouteToggle() {
  const addButton = document.getElementById("addRoute2");
  const removeButton = document.getElementById("removeRoute2");
  const route2Fields = document.getElementById("route2Fields");
  if (!addButton || !removeButton || !route2Fields) return;

  addButton.addEventListener("click", () => {
    route2Fields.hidden = false;
    addButton.hidden = true;
  });

  removeButton.addEventListener("click", () => {
    route2Fields.hidden = true;
    addButton.hidden = false;
    document.getElementById("file2").value = "";
  });
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
    setStatus("Selecteer eerst een GPX bestand voor route 1.");
    return;
  }

  const date = document.getElementById("rideDate").value;
  const time = document.getElementById("rideTime").value;
  if (!date || !time) {
    setStatus("Kies een datum en tijd voor de rit.");
    return;
  }

  const direction = document.getElementById("direction").value;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("date", date);
  formData.append("time", time);
  formData.append("direction", direction);

  const route2Visible = !document.getElementById("route2Fields").hidden;
  const file2 = route2Visible ? document.getElementById("file2").files[0] : null;
  if (route2Visible && !file2) {
    setStatus("Selecteer een GPX bestand voor route 2, of verwijder route 2.");
    return;
  }
  if (file2) {
    formData.append("file2", file2);
    formData.append("direction2", document.getElementById("direction2").value);
  }

  setStatus("Bezig met analyseren...");

  try {
    const response = await fetch("/upload", { method: "POST", body: formData });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Server fout");
    }

    clearMap();
    updateRouteCards(data.routes);
    drawRoutes(data.routes);
    setStatus("Analyse klaar.");
  } catch (error) {
    console.error(error);
    setStatus("Fout: " + error.message);
  }
}

// ============================
// INFO PANEL
// ============================

function updateRouteCards(routes) {
  const container = document.getElementById("routeCards");
  if (!container) return;

  container.innerHTML = routes.map((entry, index) => routeCardHTML(entry, index)).join("");
}

function routeCardHTML(entry, index) {
  const summary = entry.wind.summary;
  const direction = degreesToCompass(Number(summary.wind_direction));
  const dashClass = index === 0 ? "swatch-line-solid" : "swatch-line-dashed";

  return `
    <div class="card route-card">
      <h2><span class="swatch ${dashClass}"></span>${escapeHtml(entry.label)}</h2>
      <table class="summary">
        <tr><td>Afstand</td><td>${Number(entry.route.distance_km).toFixed(2)} km</td></tr>
        <tr><td>Punten</td><td>${entry.route.points.length}</td></tr>
        <tr><td>Tegenwind</td><td>${summary.tegenwind_segmenten} segmenten</td></tr>
        <tr><td>Meewind</td><td>${summary.meewind_segmenten} segmenten</td></tr>
        <tr><td>Zijwind</td><td>${summary.zijwind_segmenten} segmenten</td></tr>
        <tr><td>Gemiddelde wind</td><td>${summary.gemiddelde_windsnelheid} km/u</td></tr>
        <tr><td>Windrichting</td><td>${direction}</td></tr>
      </table>
    </div>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ============================
// ROUTES TEKENEN
// ============================

function drawRoutes(routes) {
  if (!map) return;

  const bounds = L.latLngBounds();

  routes.forEach((entry, index) => {
    drawWindSegments(entry.wind.segments, index, bounds);
  });

  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [20, 20] });
  }
}

function drawWindSegments(segments, routeIndex, bounds) {
  const dashArray = ROUTE_DASH_ARRAYS[routeIndex] || null;
  arrowDistance = 0;

  segments.forEach((segment) => {
    const color = CLASSIFICATION_COLORS[segment.classification] || DEFAULT_SEGMENT_COLOR;

    const line = L.polyline(segment.coordinates, {
      color,
      weight: 6,
      dashArray,
    }).addTo(map);

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

  const arrow = L.polyline([[midLat, midLon], tip, left, tip, right], { color: "#1a1a1a", weight: 3 }).addTo(map);
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
