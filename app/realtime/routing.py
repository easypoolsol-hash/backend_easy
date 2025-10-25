"""WebSocket URL routing for realtime app."""

from django.urls import re_path

from realtime import consumers

websocket_urlpatterns = [
    re_path(r"ws/dashboard/$", consumers.DashboardConsumer.as_asgi()),
    re_path(r"ws/bus-tracking/$", consumers.BusTrackingConsumer.as_asgi()),
]
