"""WebSocket authentication middleware for JWT tokens."""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken


class JWTAuthMiddleware(BaseMiddleware):
    """
    JWT authentication middleware for WebSocket connections.

    Extracts JWT token from query parameter and authenticates user.
    Used for: Dashboard WebSocket (?token=JWT)

    Pattern: Fortune 500 standard - token in query string for WebSocket
    """

    async def __call__(self, scope, receive, send):
        """Authenticate WebSocket connection using JWT token from query params."""
        # Extract token from query string
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            # Validate and decode JWT token
            user = await self.get_user_from_token(token)
            scope["user"] = user
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        """
        Validate JWT token and return user.

        Returns:
            User object if token is valid
            AnonymousUser if token is invalid/expired
        """
        try:
            # Decode and validate JWT token
            access_token = AccessToken(token)
            user_id = access_token["user_id"]

            # Import here to avoid circular import
            from users.models import User

            user = User.objects.get(user_id=user_id)
            return user
        except Exception:
            # Token invalid, expired, or user not found
            return AnonymousUser()
