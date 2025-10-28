# Firebase Authentication Setup - Backend Easy

## Current Status

**Frontend Easy Integration: COMPLETE**
- Firebase Admin SDK installed
- FirebaseAuthentication class implemented
- Authentication chain configured
- Environment variable setup added

## Setup Instructions

### 1. Download Firebase Service Account Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Project Settings (gear icon) > Service Accounts
4. Click "Generate New Private Key"
5. Save the JSON file securely

### 2. Configure Environment Variable

Add to your `.env` file (create if doesn't exist):

```bash
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=/path/to/your/service-account-key.json
```

**Windows example:**
```bash
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=C:\Users\lalit\firebase\service-account-key.json
```

### 3. Test the Setup

```bash
cd backend_easy
.venv/Scripts/python.exe app/manage.py runserver
```

Test with curl:
```bash
curl -H "Authorization: Bearer <firebase_id_token>" http://localhost:8000/api/v1/users/me/
```

## How It Works

### Authentication Flow

1. Frontend Easy sends Firebase ID token in Authorization header:
   ```
   Authorization: Bearer <firebase_id_token>
   ```

2. Backend validates token using Firebase Admin SDK

3. Backend creates/updates Django user from Firebase claims:
   - username = Firebase UID
   - email from Firebase
   - name from Firebase

4. Request proceeds with authenticated Django user

### Authentication Chain

Configured in [settings.py:205](app/bus_kiosk_backend/settings.py#L205):

```python
"DEFAULT_AUTHENTICATION_CLASSES": [
    "bus_kiosk_backend.core.authentication.FirebaseAuthentication",  # Frontend Easy
    "rest_framework_simplejwt.authentication.JWTAuthentication",     # Legacy users
    "kiosks.authentication.KioskJWTAuthentication",                  # Bus kiosks
    "rest_framework.authentication.SessionAuthentication",
]
```

### Implementation

See [core/authentication.py](app/bus_kiosk_backend/core/authentication.py) for the complete FirebaseAuthentication class.

## Bus Kiosk Migration Plan

**Current:** HMAC activation tokens + long-lived JWT (60 days)
**Proposed:** Firebase Custom Tokens for enhanced security

### Phase 1: Enhanced Security (Keep Current Architecture)

**Immediate improvements without Firebase migration:**

1. **Add Device Fingerprinting**
   - Hardware ID validation
   - MAC address binding
   - TPM attestation (if available)

2. **Token Rotation**
   - Reduce refresh token lifetime: 60 days → 7 days
   - Auto-rotation on heartbeat (every 30 minutes)
   - Revoke on suspicious activity

3. **Certificate Pinning**
   - Pin backend SSL certificate
   - Prevent MITM attacks

4. **Rate Limiting**
   - Per-device rate limits
   - Exponential backoff on failures

### Phase 2: Firebase Custom Tokens (Optional)

**Benefits:**
- Centralized token management
- Built-in token rotation
- Firebase security rules
- Unified authentication across all clients

**Migration Steps:**

1. **Backend Changes**
   ```python
   # kiosks/views.py - activate endpoint
   from firebase_admin import auth

   def activate_kiosk(request):
       kiosk = validate_activation_token(request.data['token'])

       # Create Firebase custom token
       custom_token = auth.create_custom_token(
           uid=kiosk.kiosk_id,
           developer_claims={
               'kiosk': True,
               'bus_id': kiosk.bus.bus_id,
               'firmware_version': kiosk.firmware_version
           }
       )

       return Response({'firebase_token': custom_token})
   ```

2. **Kiosk Client Changes**
   - Add Firebase Flutter SDK
   - Sign in with custom token
   - Send Firebase ID token to backend

3. **Update KioskJWTAuthentication**
   - Accept Firebase tokens from kiosks
   - Validate custom claims
   - Extract kiosk_id from token

### Recommendation

**Start with Phase 1** - Enhanced security without architectural changes:
- No client updates needed
- Immediate security improvements
- Minimal development effort
- Compatible with existing kiosks in the field

**Phase 2 later** if you need:
- Centralized token management dashboard
- Multi-platform kiosk support
- Firebase security rules integration

## Security Considerations

### Token Storage
- Frontend Easy: Browser secure storage (HttpOnly cookies recommended)
- Bus Kiosks: Encrypted local storage with device binding

### Token Expiry
- Frontend Easy: 1 hour (Firebase default)
- Bus Kiosks: 15 minutes (current) with auto-refresh

### Audit Logging
All authentication events logged in AuditLog model with:
- User/Kiosk ID
- IP address
- Timestamp
- Action type

## Production Checklist

- [ ] Download Firebase service account key
- [ ] Add FIREBASE_SERVICE_ACCOUNT_KEY_PATH to production .env
- [ ] Set proper file permissions on service account key (chmod 600)
- [ ] Test authentication with real Firebase token
- [ ] Configure CORS for production domain
- [ ] Enable Firebase security rules
- [ ] Set up Firebase monitoring alerts
- [ ] Document token refresh flow for frontend
