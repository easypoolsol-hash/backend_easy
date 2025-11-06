"""
Google Maps Polyline Generator

Generates encoded polylines for bus routes using Google Maps Directions API.
Uses shared storage bucket for boarding event images.
"""

import logging

from django.conf import settings
import requests

logger = logging.getLogger(__name__)


class PolylineGenerationError(Exception):
    """Raised when polyline generation fails"""

    pass


def generate_route_polyline(waypoints: list[tuple[float, float]]) -> str:
    """
    Generate encoded polyline from list of waypoints using Google Directions API.

    Args:
        waypoints: List of (latitude, longitude) tuples

    Returns:
        Encoded polyline string

    Raises:
        PolylineGenerationError: If API call fails or no valid route found
    """
    if len(waypoints) < 2:
        raise PolylineGenerationError("Need at least 2 waypoints to generate a route")

    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)
    if not api_key:
        raise PolylineGenerationError("GOOGLE_MAPS_API_KEY not configured in settings")

    # Origin and destination
    origin = f"{waypoints[0][0]},{waypoints[0][1]}"
    destination = f"{waypoints[-1][0]},{waypoints[-1][1]}"

    # Intermediate waypoints (if any)
    waypoint_params = []
    if len(waypoints) > 2:
        for lat, lng in waypoints[1:-1]:
            waypoint_params.append(f"{lat},{lng}")

    # Build API request
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": api_key,
        "mode": "driving",
    }

    if waypoint_params:
        params["waypoints"] = "|".join(waypoint_params)

    try:
        logger.info(f"Requesting polyline for route: {origin} -> {destination}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get("status") != "OK":
            error_msg = data.get("error_message", data.get("status"))
            raise PolylineGenerationError(f"Google Maps API error: {error_msg}")

        routes = data.get("routes", [])
        if not routes:
            raise PolylineGenerationError("No routes found")

        # Get the encoded polyline from the first route
        polyline = routes[0]["overview_polyline"]["points"]

        logger.info(f"Successfully generated polyline (length: {len(polyline)})")
        return polyline

    except requests.RequestException as e:
        logger.error(f"HTTP error while generating polyline: {e}")
        raise PolylineGenerationError(f"Failed to call Google Maps API: {e}") from e
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected API response format: {e}")
        raise PolylineGenerationError(f"Invalid API response format: {e}") from e


def generate_polyline_from_stops(stops: list) -> str | None:
    """
    Generate polyline from BusStop objects.

    Args:
        stops: List of BusStop model instances with latitude/longitude

    Returns:
        Encoded polyline string or None if generation fails
    """
    if not stops:
        logger.warning("No stops provided for polyline generation")
        return None

    try:
        waypoints = [(float(stop.latitude), float(stop.longitude)) for stop in stops]
        return generate_route_polyline(waypoints)
    except PolylineGenerationError as e:
        logger.error(f"Failed to generate polyline: {e}")
        return None
