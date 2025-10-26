"""
Google Maps API Proxy
Proxies Maps requests to hide API key from frontend (security best practice)
"""
import requests
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geocode(request):
    """
    Proxy for Google Maps Geocoding API
    GET /api/v1/maps/geocode?address=123+Main+St
    """
    address = request.query_params.get('address')

    if not address:
        return Response(
            {'error': 'address parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get Google Maps API key from environment
    api_key = settings.GOOGLE_MAPS_API_KEY

    if not api_key:
        return Response(
            {'error': 'Google Maps API key not configured'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Call Google Maps Geocoding API
    try:
        response = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={
                'address': address,
                'key': api_key
            },
            timeout=10
        )
        response.raise_for_status()

        # Return Google's response directly
        return Response(response.json())

    except requests.RequestException as e:
        return Response(
            {'error': f'Failed to call Google Maps API: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def places_autocomplete(request):
    """
    Proxy for Google Maps Places Autocomplete API
    GET /api/v1/maps/autocomplete?input=123+Main
    """
    input_text = request.query_params.get('input')

    if not input_text:
        return Response(
            {'error': 'input parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    api_key = settings.GOOGLE_MAPS_API_KEY

    if not api_key:
        return Response(
            {'error': 'Google Maps API key not configured'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        response = requests.get(
            'https://maps.googleapis.com/maps/api/place/autocomplete/json',
            params={
                'input': input_text,
                'key': api_key
            },
            timeout=10
        )
        response.raise_for_status()

        return Response(response.json())

    except requests.RequestException as e:
        return Response(
            {'error': f'Failed to call Google Maps API: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY
        )
