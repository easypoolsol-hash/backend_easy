"""
Firebase Authentication for Frontend Easy

This module provides Firebase token verification for the Frontend Easy
Flutter app. It maintains backward compatibility with existing JWT
authentication for Bus Kiosks.
"""

import logging

from django.contrib.auth import get_user_model
from firebase_admin import auth
from rest_framework import authentication, exceptions

User = get_user_model()

logger = logging.getLogger(__name__)


class FirebaseAuthentication(authentication.BaseAuthentication):
    """
    Firebase Authentication for Frontend Easy

    Verifies Firebase ID tokens sent from the Flutter web app.
    Creates or updates Django users based on Firebase user data.

    Expected header: Authorization: Bearer <firebase_id_token>
    """

    def authenticate(self, request):
        """
        Authenticate the request using Firebase ID token.

        Returns:
            Tuple of (User, None) if authentication succeeds
            None if no auth header or not a Firebase token
            (let other auth classes handle it)
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header:
            return None

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            decoded_token = auth.verify_id_token(token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email')
            name = decoded_token.get('name')

            user, created = User.objects.get_or_create(
                username=firebase_uid,
                defaults={
                    'email': email or '',
                    'first_name': name.split(' ')[0] if name else '',
                    'last_name': ' '.join(name.split(' ')[1:]) if name and len(name.split(' ')) > 1 else '',
                }
            )

            if user.email != (email or ''):
                user.email = email or ''
                user.save(update_fields=['email'])

            if created:
                logger.info(
                    f"Created new user from Firebase: {firebase_uid} ({email})"
                )
            else:
                logger.debug(
                    "Authenticated existing user from Firebase: "
                    f"{firebase_uid}"
                )

            return (user, None)

        except auth.ExpiredIdTokenError as e:
            logger.warning("Firebase token expired")
            raise exceptions.AuthenticationFailed(
                'Firebase token has expired'
            ) from e

        except auth.RevokedIdTokenError as e:
            logger.warning("Firebase token revoked")
            raise exceptions.AuthenticationFailed(
                'Firebase token has been revoked'
            ) from e

        except auth.InvalidIdTokenError as e:
            logger.warning("Invalid Firebase token")
            raise exceptions.AuthenticationFailed(
                'Invalid Firebase token'
            ) from e

        except Exception as e:
            logger.error(f"Firebase authentication error: {e}")
            raise exceptions.AuthenticationFailed(
                'Firebase authentication failed'
            ) from e
