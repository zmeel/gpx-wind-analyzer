"""Combine a parsed GPX route with wind data into a per-segment wind analysis."""

import logging
from datetime import datetime
from typing import TypedDict

from sampler import DEFAULT_INTERVAL_M, sample_index_for_distance, sample_wind_points
from weather import get_wind_batch
from wind import wind_effect

logger = logging.getLogger(__name__)


class SegmentResult(TypedDict):
    index: int
    coordinates: list[list[float]]
    bearing: float
    wind_speed: float
    wind_direction: float
    component: float
    classification: str


class WindSummary(TypedDict):
    tegenwind_segmenten: int
    meewind_segmenten: int
    zijwind_segmenten: int
    windsnelheden: list[float]
    windrichtingen: list[float]
    gemiddelde_windsnelheid: float
    wind_direction: float


def _empty_summary() -> WindSummary:
    return {
        "tegenwind_segmenten": 0,
        "meewind_segmenten": 0,
        "zijwind_segmenten": 0,
        "windsnelheden": [],
        "windrichtingen": [],
        "gemiddelde_windsnelheid": 0.0,
        "wind_direction": 0.0,
    }


def _finalize_summary(summary: WindSummary) -> None:
    speeds = summary["windsnelheden"]
    directions = summary["windrichtingen"]
    summary["gemiddelde_windsnelheid"] = round(sum(speeds) / len(speeds), 1) if speeds else 0.0
    summary["wind_direction"] = round(sum(directions) / len(directions), 0) if directions else 0.0


async def analyze_segments(segments: list[dict], ride_dt: datetime) -> dict:
    """Fetch wind data for a route and classify every segment as head/tail/crosswind.

    `segments` must come from `gpx_parser.parse_gpx` (or `reverse_route`), so
    each has a bearing and cumulative distance already computed.
    """
    wind_points = sample_wind_points(segments)
    weather_points = await get_wind_batch(
        [{"lat": p["lat"], "lon": p["lon"]} for p in wind_points],
        ride_dt,
    )

    results: list[SegmentResult] = []
    summary = _empty_summary()

    for segment in segments:
        sample_index = sample_index_for_distance(
            segment["cumulative_distance_m"], len(weather_points), DEFAULT_INTERVAL_M
        )
        reading = weather_points[sample_index]
        wind_speed = reading["wind_speed_10m"]
        wind_direction = reading["wind_direction_10m"]

        effect = wind_effect(segment["bearing"], wind_direction, wind_speed)

        summary[f"{effect['classification']}_segmenten"] += 1
        summary["windsnelheden"].append(wind_speed)
        summary["windrichtingen"].append(wind_direction)

        results.append(
            {
                "index": segment["index"],
                "coordinates": [
                    [segment["start"]["lat"], segment["start"]["lon"]],
                    [segment["end"]["lat"], segment["end"]["lon"]],
                ],
                "bearing": round(segment["bearing"], 1),
                "wind_speed": round(wind_speed, 1),
                "wind_direction": round(wind_direction, 0),
                "component": effect["component"],
                "classification": effect["classification"],
            }
        )

    _finalize_summary(summary)
    logger.info(
        "Analyzed %d segments: %d tegenwind, %d meewind, %d zijwind",
        len(results),
        summary["tegenwind_segmenten"],
        summary["meewind_segmenten"],
        summary["zijwind_segmenten"],
    )

    return {"segments": results, "summary": summary}
