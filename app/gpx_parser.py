"""GPX parsing: turn a .gpx file into points, distance/bearing segments and totals."""

import math
from pathlib import Path
from typing import TypedDict

import gpxpy

from bearing import calculate_bearing

EARTH_RADIUS_M = 6_371_000


class Point(TypedDict):
    lat: float
    lon: float
    elevation: float | None


class Segment(TypedDict):
    index: int
    start: Point
    end: Point
    midpoint: dict
    distance_m: float
    cumulative_distance_m: float
    bearing: float


class GpxRoute(TypedDict):
    points: list[Point]
    segments: list[Segment]
    coordinates: list[list[float]]
    distance_km: float
    total_distance_m: float
    start: Point
    end: Point


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates, in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_gpx(path: str | Path) -> GpxRoute:
    """Parse a GPX file into a route with per-segment distance and bearing.

    Raises ValueError if the file contains fewer than two track points.
    """
    with open(path, "r", encoding="utf-8") as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    points: list[Point] = [
        {"lat": point.latitude, "lon": point.longitude, "elevation": point.elevation}
        for track in gpx.tracks
        for segment in track.segments
        for point in segment.points
    ]

    if len(points) < 2:
        raise ValueError("GPX bevat onvoldoende punten (minimaal 2 vereist).")

    segments: list[Segment] = []
    total_distance = 0.0

    for index, (start, end) in enumerate(zip(points[:-1], points[1:])):
        distance = haversine(start["lat"], start["lon"], end["lat"], end["lon"])
        total_distance += distance

        segments.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "midpoint": {
                    "lat": (start["lat"] + end["lat"]) / 2,
                    "lon": (start["lon"] + end["lon"]) / 2,
                },
                "distance_m": round(distance, 1),
                "cumulative_distance_m": round(total_distance, 1),
                "bearing": calculate_bearing(start["lat"], start["lon"], end["lat"], end["lon"]),
            }
        )

    return {
        "points": points,
        "segments": segments,
        "coordinates": [[p["lat"], p["lon"]] for p in points],
        "distance_km": round(total_distance / 1000, 2),
        "total_distance_m": round(total_distance, 1),
        "start": points[0],
        "end": points[-1],
    }


def reverse_route(route: GpxRoute) -> GpxRoute:
    """Return a new route with the direction of travel reversed.

    Builds new segment dicts rather than mutating the originals, and
    recomputes bearings/cumulative distance for the reversed direction
    (a segment reversed in place would keep its old, now-wrong bearing).
    """
    reversed_points = list(reversed(route["points"]))

    reversed_segments: list[Segment] = []
    total_distance = 0.0

    for index, (start, end) in enumerate(zip(reversed_points[:-1], reversed_points[1:])):
        distance = haversine(start["lat"], start["lon"], end["lat"], end["lon"])
        total_distance += distance

        reversed_segments.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "midpoint": {
                    "lat": (start["lat"] + end["lat"]) / 2,
                    "lon": (start["lon"] + end["lon"]) / 2,
                },
                "distance_m": round(distance, 1),
                "cumulative_distance_m": round(total_distance, 1),
                "bearing": calculate_bearing(start["lat"], start["lon"], end["lat"], end["lon"]),
            }
        )

    return {
        "points": reversed_points,
        "segments": reversed_segments,
        "coordinates": [[p["lat"], p["lon"]] for p in reversed_points],
        "distance_km": route["distance_km"],
        "total_distance_m": route["total_distance_m"],
        "start": reversed_points[0],
        "end": reversed_points[-1],
    }
