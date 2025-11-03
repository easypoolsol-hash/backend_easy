from django.conf import settings
import googlemaps


class LocationService:
    """Service for geocoding addresses to coordinates"""

    def __init__(self):
        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not configured in settings")
        self.gmaps = googlemaps.Client(key=api_key)

    def geocode_address(self, address: str) -> dict:
        """
        Convert address to coordinates using Google Geocoding API.

        Args:
            address: Address string to geocode

        Returns:
            dict with keys: latitude, longitude, formatted_address

        Raises:
            ValueError: If location not found
        """
        try:
            result = self.gmaps.geocode(address)

            if not result:
                raise ValueError(f"Location not found: {address}")

            location = result[0]["geometry"]["location"]
            formatted_address = result[0]["formatted_address"]

            return {"latitude": location["lat"], "longitude": location["lng"], "formatted_address": formatted_address}
        except Exception as e:
            raise ValueError(f"Geocoding failed: {e!s}") from e


class PolylineService:
    """Service for generating route polylines"""

    def __init__(self):
        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not configured in settings")
        self.gmaps = googlemaps.Client(key=api_key)

    def generate_route_polyline(self, waypoints: list) -> str:
        """
        Generate encoded polyline from list of waypoints using Google Directions API.

        Args:
            waypoints: List of (latitude, longitude) tuples

        Returns:
            Encoded polyline string
        """
        if len(waypoints) < 2:
            raise ValueError("At least 2 waypoints required for route")

        origin = waypoints[0]
        destination = waypoints[-1]
        intermediate = waypoints[1:-1] if len(waypoints) > 2 else None

        try:
            directions = self.gmaps.directions(
                origin=origin,
                destination=destination,
                waypoints=intermediate,
                optimize_waypoints=False,  # Keep original order
                mode="driving",
            )

            if not directions:
                raise ValueError("No route found")

            # Return encoded polyline
            return directions[0]["overview_polyline"]["points"]
        except Exception as e:
            raise ValueError(f"Polyline generation failed: {e!s}") from e
