"""Wind-component calculation relative to a direction of travel.

Wind direction here follows meteorological convention: the direction the
wind is blowing FROM, not the direction it is blowing towards. A tailwind
therefore comes from the direction opposite the bike's bearing.
"""

import math

HEADWIND_THRESHOLD_KMH = 5.0
TAILWIND_THRESHOLD_KMH = -5.0


def normalize_angle(angle: float) -> float:
    """Wrap an angle in degrees to the range (-180, 180]."""
    return (angle + 180) % 360 - 180


def wind_component(bike_bearing: float, wind_direction: float, wind_speed: float) -> float:
    """Effective headwind/tailwind component in km/h.

    Positive = headwind, negative = tailwind, near zero = crosswind.
    """
    angle = normalize_angle(wind_direction - bike_bearing)
    return round(wind_speed * math.cos(math.radians(angle)), 1)


def classify_wind(component: float) -> str:
    """Classify a wind component as headwind/tailwind/crosswind (Dutch labels, matching the UI)."""
    if component >= HEADWIND_THRESHOLD_KMH:
        return "tegenwind"
    if component <= TAILWIND_THRESHOLD_KMH:
        return "meewind"
    return "zijwind"


def wind_effect(bike_bearing: float, wind_direction: float, wind_speed: float) -> dict:
    """Combined component + classification for a single segment."""
    component = wind_component(bike_bearing, wind_direction, wind_speed)
    return {
        "component": component,
        "classification": classify_wind(component),
    }
