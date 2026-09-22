"""Wind lookups against Open-Meteo.

Open-Meteo splits weather data across two endpoints:

- ``/v1/forecast`` covers roughly the last 92 days through the next 16 days
  (its "historical forecast" window), which is what we need for anything
  from a recent ride up to a ride planned in the near future.
- ``/v1/archive`` covers the full historical record (back to the 1940s)
  but does not extend into the future at all.

We pick whichever endpoint covers the requested ride date. Dates further
than the forecast horizon in the future are rejected up front with a clear
error, rather than silently returning empty or zeroed wind data.

These endpoint boundaries are Open-Meteo's documented behaviour at the time
this was written; if wind lookups start failing for dates that should be in
range, check https://open-meteo.com/en/docs for current limits.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Iterator, TypedDict

import httpx

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

FORECAST_PAST_LIMIT_DAYS = 92
FORECAST_FUTURE_LIMIT_DAYS = 16

TIMEZONE = "Europe/Amsterdam"
BATCH_SIZE = 20
REQUEST_TIMEOUT_S = 60


class LatLon(TypedDict):
    lat: float
    lon: float


class WindReading(TypedDict):
    wind_speed_10m: float
    wind_direction_10m: float


def _chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def validate_ride_datetime(ride_dt: datetime, today: date | None = None) -> None:
    """Raise ValueError if `ride_dt` is further ahead than Open-Meteo's forecast horizon."""
    today = today or date.today()
    days_ahead = (ride_dt.date() - today).days
    if days_ahead > FORECAST_FUTURE_LIMIT_DAYS:
        raise ValueError(
            f"Weersverwachtingen zijn maximaal {FORECAST_FUTURE_LIMIT_DAYS} dagen vooruit "
            f"beschikbaar. Kies een datum tot en met "
            f"{(today + timedelta(days=FORECAST_FUTURE_LIMIT_DAYS)).isoformat()}."
        )


def choose_endpoint(ride_dt: datetime, today: date | None = None) -> str:
    """Return the Open-Meteo base URL that covers `ride_dt`."""
    today = today or date.today()
    days_ago = (today - ride_dt.date()).days
    if days_ago <= FORECAST_PAST_LIMIT_DAYS:
        return FORECAST_URL
    return ARCHIVE_URL


def _closest_hourly_reading(hourly: dict, ride_dt: datetime) -> WindReading:
    times = hourly.get("time", [])
    speeds = hourly.get("wind_speed_10m", [])
    directions = hourly.get("wind_direction_10m", [])

    if not times:
        return {"wind_speed_10m": 0.0, "wind_direction_10m": 0.0}

    best_index = 0
    best_delta = None
    for i, timestamp in enumerate(times):
        delta = abs((datetime.fromisoformat(timestamp) - ride_dt).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_index = i

    return {
        "wind_speed_10m": speeds[best_index],
        "wind_direction_10m": directions[best_index],
    }


async def _fetch_batch(client: httpx.AsyncClient, base_url: str, points: list[LatLon], ride_dt: datetime) -> list[WindReading]:
    latitudes = ",".join(str(round(p["lat"], 6)) for p in points)
    longitudes = ",".join(str(round(p["lon"], 6)) for p in points)
    ride_date = ride_dt.date().isoformat()

    response = await client.get(
        base_url,
        params={
            "latitude": latitudes,
            "longitude": longitudes,
            "start_date": ride_date,
            "end_date": ride_date,
            "hourly": "wind_speed_10m,wind_direction_10m",
            "wind_speed_unit": "kmh",
            "timezone": TIMEZONE,
        },
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    data = response.json()

    locations = data if isinstance(data, list) else [data]
    return [_closest_hourly_reading(location.get("hourly", {}), ride_dt) for location in locations]


async def get_wind_batch(points: list[LatLon], ride_dt: datetime) -> list[WindReading]:
    """Fetch a wind reading for each point, closest in time to `ride_dt`.

    Raises ValueError if `ride_dt` is beyond the forecast horizon, or
    httpx.HTTPError if Open-Meteo is unreachable or returns an error.
    """
    validate_ride_datetime(ride_dt)
    base_url = choose_endpoint(ride_dt)
    logger.info("Fetching wind data from %s for %d point(s) at %s", base_url, len(points), ride_dt)

    results: list[WindReading] = []
    async with httpx.AsyncClient() as client:
        for batch in _chunks(points, BATCH_SIZE):
            results.extend(await _fetch_batch(client, base_url, batch, ride_dt))

    return results
