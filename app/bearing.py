"""Great-circle bearing calculation between two coordinates."""

import math


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial compass bearing (degrees, 0-360) from point 1 to point 2."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)

    bearing = math.degrees(math.atan2(x, y))
    return round((bearing + 360) % 360, 1)
