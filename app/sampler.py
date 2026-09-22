"""Pick a sparse set of route points to query the wind API for.

Querying the weather API for every GPX point would be far too many
requests, so we sample one lookup point roughly every `interval_m`
meters of route distance instead.
"""

from typing import TypedDict

DEFAULT_INTERVAL_M = 10_000


class WindSample(TypedDict):
    distance_m: float
    lat: float
    lon: float
    segment_index: int


def sample_wind_points(segments: list[dict], interval_m: int = DEFAULT_INTERVAL_M) -> list[WindSample]:
    """Return one sample point per `interval_m` of cumulative route distance.

    Always returns at least one sample (the first segment's midpoint) if
    the route has any segments at all, even if it's shorter than one interval.
    """
    samples: list[WindSample] = []
    next_distance = interval_m

    for segment in segments:
        if segment["cumulative_distance_m"] >= next_distance:
            samples.append(
                {
                    "distance_m": segment["cumulative_distance_m"],
                    "lat": segment["midpoint"]["lat"],
                    "lon": segment["midpoint"]["lon"],
                    "segment_index": segment["index"],
                }
            )
            next_distance += interval_m

    if not samples and segments:
        first = segments[0]
        samples.append(
            {
                "distance_m": 0,
                "lat": first["midpoint"]["lat"],
                "lon": first["midpoint"]["lon"],
                "segment_index": first["index"],
            }
        )

    return samples


def sample_index_for_distance(cumulative_distance_m: float, sample_count: int, interval_m: int = DEFAULT_INTERVAL_M) -> int:
    """Map a segment's cumulative distance to the wind sample that covers it.

    Samples are taken every `interval_m`, so the sample covering a given
    distance is simply that distance divided by the interval, clamped to
    the last available sample.
    """
    index = int(cumulative_distance_m // interval_m)
    return min(index, sample_count - 1)
