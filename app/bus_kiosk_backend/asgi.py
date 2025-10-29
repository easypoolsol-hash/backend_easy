"""
ASGI config for bus_kiosk_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

Supports both HTTP and WebSocket protocols via Django Channels.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

# Set Django settings module - check for override from environment (e.g., Makefile)
# If DJANGO_SETTINGS_MODULE is set in environment, use it; otherwise default to production settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.settings")

# Initialize Django ASGI application early to ensure AppRegistry is populated
# before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import WebSocket routing after Django setup
from realtime.middleware import JWTAuthMiddleware  # noqa: E402
from realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # HTTP requests
        "http": django_asgi_app,
        # WebSocket requests - JWT authentication for dashboard
        "websocket": AllowedHostsOriginValidator(JWTAuthMiddleware(URLRouter(websocket_urlpatterns))),
    }
)
