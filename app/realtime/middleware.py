"""WebSocket authentication middleware for JWT tokens."""

import os
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
import firebase_admin
from firebase_admin import auth, credentials


class JWTAuthMiddleware(BaseMiddleware):
    """
    JWT authentication middleware for WebSocket connections.

    Extracts JWT token from query parameter and authenticates user.
    Used for: Dashboard WebSocket (?token=JWT)

    Pattern: Fortune 500 standard - token in query string for WebSocket
    """

    def __init__(self, inner):
        super().__init__(inner)
        # Initialize Firebase Admin SDK if not already initialized
        if not firebase_admin._apps:
            cred_path = os.path.join(os.path.dirname(__file__), "..", "..", "firebase_keys", "service-account-key.json")
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)

    async def __call__(self, scope, receive, send):
        """Authenticate WebSocket connection using JWT token from query params."""
        from django.contrib.auth.models import AnonymousUser

        # Extract token from query string
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            # Validate Firebase JWT token
            user = await self.get_user_from_firebase_token(token)
            scope["user"] = user
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_firebase_token(self, token):
        """
        Validate Firebase JWT token and return Django user.

        Returns:
            User object if token is valid and user exists
            AnonymousUser if token is invalid/expired or user not found
        """
        from django.contrib.auth.models import AnonymousUser

        from users.models import User

        try:
            # Verify Firebase token
            decoded_token = auth.verify_id_token(token)
            firebase_uid = decoded_token["uid"]
            email = decoded_token.get("email")

            # Get or create user by Firebase UID
            user, _created = User.objects.get_or_create(
                username=firebase_uid,
                defaults={
                    "email": email or "",
                    "first_name": (decoded_token.get("name", "").split()[0] if decoded_token.get("name") else ""),
                    "last_name": (
                        " ".join(decoded_token.get("name", "").split()[1:])
                        if (decoded_token.get("name") and len(decoded_token.get("name", "").split()) > 1)
                        else ""
                    ),
                },
            )

            # Emit signal for last_login tracking and audit logging
            # Note: request=None for WebSocket (no HTTP request object)
            from users.signals import user_authenticated

            user_authenticated.send(sender=self.__class__, user=user, request=None, auth_method="websocket")

            return user
        except Exception as e:
            # Log error but don't expose details to client
            print(f"WebSocket auth error: {e}")
            return AnonymousUser()
