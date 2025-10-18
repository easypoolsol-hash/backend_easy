# JWT Token Lifecycle - Imperial Authentication Architecture

## Executive Summary

The backend implements a **Fortune 500-grade JWT authentication system** that enables **autonomous kiosk operation without re-login** while maintaining **maximum security**. This document details the complete token lifecycle from activation through continuous operation.

## Core Design Principles

### 1. Autonomous Operation
- Kiosks operate independently for 60 days without human intervention
- No re-login required during normal operation
- Automatic token refresh maintains continuous authentication

### 2. Defense in Depth Security
- Multi-layer security approach (rotation, blacklist, expiration, validation)
- Stolen tokens have minimal attack window
- Remote revocation capability for compromised devices

### 3. Industry Standard Pattern
- Same approach used by Google, Amazon, Netflix, Dropbox
- RFC 6749 (OAuth 2.0) refresh token pattern
- JWT (RFC 7519) with custom claims

## Token Architecture

### Two-Token System

```yaml
Access Token:
  lifetime: 15 minutes
  purpose: Active authentication for API requests
  storage: Memory (client-side)
  security: Short-lived to limit theft impact

Refresh Token:
  lifetime: 60 days
  purpose: Generate new access tokens
  storage: Secure storage (client-side)
  security: Rotates on every use, old token blacklisted
```

**Configuration Location**: [settings.py:152-169](../app/bus_kiosk_backend/settings.py#L152-L169)

```python
SIMPLE_JWT = {
    # Access Token (Short-lived for security - if stolen, only works 15 min)
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),

    # Refresh Token (60 days for 2-month holidays - kiosk autonomy)
    "REFRESH_TOKEN_LIFETIME": timedelta(days=60),

    # Token Rotation (Security - old tokens become garbage every 14 min)
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    # Algorithm and signing
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
}
```

## Complete Lifecycle

### Phase 1: Kiosk Activation (One-Time Setup)

**Endpoint**: `POST /api/v1/kiosks/activate/`
**Implementation**: [authentication.py:77-137](../app/kiosks/authentication.py#L77-L137)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Admin Creates Activation Token                     │
├─────────────────────────────────────────────────────────────┤
│ - Admin creates kiosk in admin panel                        │
│ - System generates cryptographic activation token           │
│ - Token hashed with HMAC-SHA256 + SECRET_KEY                │
│ - Only hash stored in database (plaintext never stored)     │
│ - Admin receives plaintext token (one-time display)         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Kiosk Activation Request                            │
├─────────────────────────────────────────────────────────────┤
│ POST /api/v1/kiosks/activate/                               │
│ {                                                            │
│   "kiosk_id": "KIOSK-SCHOOL-001",                           │
│   "activation_token": "8Jz4Y-x9K2mQ_r5WvLp3NcTg..."         │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Server-Side Validation                              │
├─────────────────────────────────────────────────────────────┤
│ ✓ Kiosk exists in database                                  │
│ ✓ Kiosk is_active = True                                    │
│ ✓ Hash submitted token with HMAC-SHA256                     │
│ ✓ Find matching token_hash in database                      │
│ ✓ Token not already used (is_used = False)                  │
│ ✓ Token not expired                                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: JWT Token Generation                                │
├─────────────────────────────────────────────────────────────┤
│ refresh = RefreshToken()                                    │
│ refresh["kiosk_id"] = "KIOSK-SCHOOL-001"                    │
│ refresh["type"] = "kiosk"                                   │
│                                                              │
│ Tokens Created:                                             │
│ - refresh_token (expires: Day 60, 23:59)                    │
│ - access_token (expires: 00:15)                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Activation Token Destroyed (WhatsApp Protection)    │
├─────────────────────────────────────────────────────────────┤
│ activation.is_used = True                                   │
│ activation.used_at = timezone.now()                         │
│ activation.save()                                           │
│                                                              │
│ → Token becomes GARBAGE (single-use security)               │
│ → Even if leaked via WhatsApp, cannot be reused             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 6: Response to Kiosk                                   │
├─────────────────────────────────────────────────────────────┤
│ {                                                            │
│   "message": "Kiosk activated successfully",                │
│   "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",                   │
│   "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",                    │
│   "kiosk_id": "KIOSK-SCHOOL-001",                           │
│   "activation_token_destroyed": true                        │
│ }                                                            │
│                                                              │
│ Kiosk stores:                                               │
│ - access_token → in-memory                                  │
│ - refresh_token → secure storage (encrypted preferences)    │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Normal Operation (Day 1-60)

**Authentication**: [authentication.py:22-74](../app/kiosks/authentication.py#L22-L74)

```
┌─────────────────────────────────────────────────────────────┐
│ Every API Request (15-minute window)                        │
├─────────────────────────────────────────────────────────────┤
│ GET /api/v1/kiosks/{kiosk_id}/check-updates/               │
│ Authorization: Bearer {access_token}                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ KioskJWTAuthentication.authenticate(request)                │
├─────────────────────────────────────────────────────────────┤
│ Step 1: Extract token from Authorization header             │
│ Step 2: Verify JWT signature (HS256 + SECRET_KEY)           │
│ Step 3: Check token not expired                             │
│ Step 4: Extract custom claims (kiosk_id, type)              │
│ Step 5: Load Kiosk object from database                     │
│ Step 6: Verify kiosk.is_active = True                       │
│                                                              │
│ Result: request.user = Kiosk object                         │
│                                                              │
│ ✅ Request proceeds to business logic                        │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: Token Refresh (Every 15 Minutes)

**Endpoint**: `POST /api/v1/auth/token/refresh/`
**Implementation**: [users/views.py:170-177](../app/users/views.py#L170-L177)

```
┌─────────────────────────────────────────────────────────────┐
│ Minute 15: Access Token Expires                             │
├─────────────────────────────────────────────────────────────┤
│ Next API request returns 401 Unauthorized                   │
│ Client detects expiration                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Client Initiates Token Refresh                              │
├─────────────────────────────────────────────────────────────┤
│ POST /api/v1/auth/token/refresh/                            │
│ {                                                            │
│   "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."                    │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Server-Side Token Rotation                                  │
├─────────────────────────────────────────────────────────────┤
│ ✓ Verify refresh token signature                            │
│ ✓ Check refresh token not expired (< 60 days)               │
│ ✓ Check refresh token not blacklisted                       │
│ ✓ Extract claims (kiosk_id, type)                           │
│                                                              │
│ Generate NEW tokens:                                        │
│ - new_refresh_token (expires: Day 60, 23:59)                │
│ - new_access_token (expires: current_time + 15 min)         │
│                                                              │
│ Blacklist old refresh token:                                │
│ - Add old_refresh_token to blacklist table                  │
│ - Token becomes GARBAGE immediately                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Response with New Tokens                                    │
├─────────────────────────────────────────────────────────────┤
│ {                                                            │
│   "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",  (new)            │
│   "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..." (new)             │
│ }                                                            │
│                                                              │
│ Client updates stored tokens:                               │
│ - access_token ← new_access_token                           │
│ - refresh_token ← new_refresh_token                         │
│                                                              │
│ ✅ Operation continues seamlessly                            │
└─────────────────────────────────────────────────────────────┘
```

### Phase 4: 60-Day Timeline

```
Day 1
├─ 00:00 - Kiosk activates
├─ 00:00-00:15 - Uses access_token_1
├─ 00:15 - Refresh → access_token_2, refresh_token_2
├─ 00:15-00:30 - Uses access_token_2
├─ 00:30 - Refresh → access_token_3, refresh_token_3
└─ ... pattern continues (96 refreshes per day)

Day 2-59
└─ Same refresh pattern (96 refreshes/day × 59 days = 5,664 refreshes)

Day 60
├─ 00:00-23:45 - Normal refresh pattern continues
├─ 23:45 - Last refresh before expiration
└─ 23:59 - refresh_token_N expires

Day 61
├─ Access token still works for 15 minutes (from last refresh)
├─ When access token expires, refresh fails
└─ Options:
    ├─ Admin creates new activation token
    └─ Kiosk re-activates (repeat Phase 1)
```

## Security Architecture

### Layer 1: Short-Lived Access Tokens

**Protection**: Limits attack window if token stolen

```
Scenario: Attacker intercepts access token
├─ Attacker window: 0-15 minutes (typically <7.5 min average)
├─ After expiration: Token becomes useless
└─ Attacker must steal refresh token for persistence
```

### Layer 2: Token Rotation

**Protection**: Prevents refresh token reuse

**Implementation**: [settings.py:158-159](../app/bus_kiosk_backend/settings.py#L158-L159)

```python
ROTATE_REFRESH_TOKENS = True      # Generate new refresh token on every refresh
BLACKLIST_AFTER_ROTATION = True   # Immediately blacklist old refresh token
```

**Attack Scenario**:
```
Legitimate Kiosk             Attacker (stolen refresh_token_1)
     │                                    │
     ├─ Refresh with token_1 ────────────┤
     │  (First to server)                 │
     ├─ Receive token_2                   │
     │  token_1 → BLACKLISTED              │
     │                                    │
     │                         Attacker tries token_1
     │                         Server: "Token blacklisted"
     │                         ❌ Attack fails
```

### Layer 3: Token Blacklist

**Protection**: Detects and blocks token reuse attacks

**Database**: `rest_framework_simplejwt.token_blacklist` app

```
Blacklist Table:
├─ Tracks all invalidated refresh tokens
├─ Checked on every refresh request
└─ Tokens remain blacklisted until natural expiration
```

**Use Cases**:
1. Token rotation (automatic)
2. User logout (manual)
3. Admin revocation (emergency)
4. Kiosk deactivation (security)

### Layer 4: HMAC-SHA256 Token Hashing

**Protection**: Prevents activation token theft from database

**Implementation**: [authentication.py:107](../app/kiosks/authentication.py#L107)

```python
submitted_hash = hmac.new(
    settings.SECRET_KEY.encode(),
    activation_token.encode(),
    sha256
).hexdigest()
```

**Security**:
- Activation tokens never stored in plaintext
- Database breach doesn't reveal usable tokens
- SECRET_KEY serves as HMAC key (must be secret)
- One-way hashing (cannot reverse to get plaintext)

### Layer 5: Active Kiosk Validation

**Protection**: Remote revocation capability

**Implementation**: [authentication.py:46-48](../app/kiosks/authentication.py#L46-L48)

```python
if not kiosk.is_active:
    raise exceptions.AuthenticationFailed("Kiosk is deactivated")
```

**Admin Control**:
```
Scenario: Kiosk device stolen
├─ Admin sets kiosk.is_active = False in admin panel
├─ Next API request with valid JWT fails authentication
├─ All future requests blocked (even with valid tokens)
└─ Stolen device becomes useless immediately
```

### Layer 6: Custom Claims Validation

**Protection**: Prevents generic JWT token attacks

**Implementation**: [authentication.py:36-39](../app/kiosks/authentication.py#L36-L39)

```python
try:
    kiosk_id = validated_token["kiosk_id"]
except KeyError:
    raise exceptions.AuthenticationFailed("Token missing kiosk_id claim")
```

**Security**:
- Ensures token contains kiosk-specific claims
- Prevents user JWT tokens from accessing kiosk endpoints
- Type-safe authentication (kiosk vs user tokens)

## Attack Surface Analysis

| Attack Vector | Protection Mechanism | Attack Window |
|--------------|---------------------|---------------|
| Access token theft | 15-minute expiration | 0-15 minutes |
| Refresh token theft | Token rotation + blacklist | Single use |
| Token reuse | Blacklist detection | None (blocked) |
| Database breach | HMAC-SHA256 hashing | None (tokens hashed) |
| Device theft | Remote deactivation | Seconds (admin action) |
| Man-in-the-middle | HTTPS + HSTS headers | None (encrypted) |
| Token forgery | Cryptographic signature | None (impossible) |
| Activation token leak | Single-use destruction | None (one-time) |
| Brute force | Rate limiting | Limited attempts |

## Client-Side Implementation Pattern

### Recommended Token Management

```dart
class AuthService {
  String? _accessToken;
  String? _refreshToken;

  // Store refresh token in secure storage
  Future<void> activate(String kioskId, String activationToken) async {
    final response = await http.post(
      '/api/v1/kiosks/activate/',
      body: {'kiosk_id': kioskId, 'activation_token': activationToken},
    );

    _accessToken = response['access'];
    _refreshToken = response['refresh'];

    // CRITICAL: Store refresh token in encrypted storage
    await _secureStorage.write(key: 'refresh_token', value: _refreshToken);
  }

  // Automatic token refresh on 401
  Future<http.Response> makeAuthenticatedRequest(String endpoint) async {
    while (true) {
      final response = await http.get(
        endpoint,
        headers: {'Authorization': 'Bearer $_accessToken'},
      );

      // Access token expired
      if (response.statusCode == 401) {
        await _refreshAccessToken();
        continue; // Retry request with new token
      }

      return response;
    }
  }

  // Token refresh
  Future<void> _refreshAccessToken() async {
    final response = await http.post(
      '/api/v1/auth/token/refresh/',
      body: {'refresh': _refreshToken},
    );

    // Update both tokens (rotation!)
    _accessToken = response['access'];
    _refreshToken = response['refresh'];

    // Update secure storage
    await _secureStorage.write(key: 'refresh_token', value: _refreshToken);
  }
}
```

### Token Storage Security

**Access Token**: In-memory only (cleared on app restart)
```dart
String? _accessToken; // Never persist to disk
```

**Refresh Token**: Encrypted secure storage
```dart
// flutter_secure_storage (iOS Keychain, Android Keystore)
final _secureStorage = FlutterSecureStorage();
await _secureStorage.write(key: 'refresh_token', value: refreshToken);
```

**Never Do**:
- ❌ Store tokens in SharedPreferences (plaintext)
- ❌ Store tokens in SQLite (unencrypted)
- ❌ Log tokens to console (leaked in logs)
- ❌ Send tokens in URL parameters (logged in web server)

## Production Deployment Checklist

### Critical Security Requirements

- [ ] **SECRET_KEY**: 50+ random characters, environment variable only
- [ ] **HTTPS**: Mandatory (tokens transmitted in headers)
- [ ] **HSTS Headers**: Enabled (force HTTPS)
- [ ] **Database Backups**: Include blacklist table
- [ ] **Monitor Blacklist Growth**: Periodic cleanup of expired tokens
- [ ] **Rate Limiting**: Prevent brute force on activation endpoint
- [ ] **Logging**: Audit trail for all activations and refreshes
- [ ] **Token Expiration**: Adjust based on security vs. convenience tradeoff

### Performance Considerations

**Blacklist Table Growth**:
```
Daily Growth = (kiosks × refreshes_per_day)
             = (100 kiosks × 96 refreshes/day)
             = 9,600 rows/day

Monthly Growth = 9,600 × 30 = 288,000 rows/month
```

**Cleanup Strategy**:
```python
# Periodic task (run daily)
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

# Delete tokens expired >7 days ago
cleanup_date = timezone.now() - timedelta(days=7)
OutstandingToken.objects.filter(expires_at__lt=cleanup_date).delete()
```

### Monitoring and Alerts

**Key Metrics**:
- Token refresh success rate (should be >99%)
- Blacklist table size (monitor growth)
- Failed authentication attempts (detect attacks)
- Token reuse attempts (blacklist hits)
- Activation token usage (detect leaks)

**Alert Triggers**:
- Refresh success rate drops below 95% → Token rotation issue
- Multiple blacklist hits for same kiosk → Token theft detected
- Activation token reuse attempts → Leaked activation token
- High failed auth rate for kiosk → Deactivated device retrying

## Testing Requirements

### Integration Tests

**Test Coverage**: [test_authentication_flow.py](../tests/integration/test_authentication_flow.py)

1. **Complete Lifecycle Test**:
   - Activate kiosk → Get tokens
   - Use access token → Verify works
   - Refresh token → Get new tokens
   - Verify custom claims preserved

2. **Token Rotation Test**:
   - Refresh token once
   - Attempt to reuse old refresh token
   - Verify blacklist blocks reuse

3. **Security Test**:
   - Deactivate kiosk via admin
   - Attempt API request with valid token
   - Verify authentication fails

4. **Expiration Test**:
   - Wait 15+ minutes (or mock time)
   - Access token should fail
   - Refresh should succeed
   - New access token should work

## Industry Comparison

### This Implementation vs. Industry Standards

**Similar Patterns**:
- **Google OAuth 2.0**: Refresh token rotation, 60-day expiration
- **Amazon Alexa**: Device activation codes, long-lived tokens
- **Netflix Device Auth**: One-time activation, autonomous operation
- **Dropbox**: Long-lived access, automatic refresh

**Advantages Over Basic JWT**:
- ✅ Token rotation (basic JWT: static tokens)
- ✅ Blacklist detection (basic JWT: no revocation)
- ✅ Remote deactivation (basic JWT: wait for expiration)
- ✅ Custom claims validation (basic JWT: generic validation)
- ✅ One-time activation (basic JWT: password login)

## References

### Implementation Files
- [settings.py](../app/bus_kiosk_backend/settings.py) - JWT configuration
- [authentication.py](../app/kiosks/authentication.py) - Token generation and validation
- [views.py](../app/kiosks/views.py) - Activation endpoint
- [users/views.py](../app/users/views.py) - Token refresh endpoint
- [urls.py](../app/bus_kiosk_backend/urls.py) - URL routing

### Test Files
- [test_authentication_flow.py](../tests/integration/test_authentication_flow.py) - Complete lifecycle tests
- [test_kiosk_auth.py](../tests/unit/test_kiosk_auth.py) - Unit tests
- [test_chaos_auth.py](../tests/integration/test_chaos_auth.py) - Security tests

### Standards
- [RFC 6749 - OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749) - Refresh token pattern
- [RFC 7519 - JWT](https://datatracker.ietf.org/doc/html/rfc7519) - JSON Web Tokens
- [RFC 2104 - HMAC](https://datatracker.ietf.org/doc/html/rfc2104) - HMAC-SHA256 hashing

## Conclusion

This JWT implementation provides **Fortune 500-grade security** while enabling **autonomous kiosk operation** for extended periods. The multi-layer security approach (rotation, blacklist, expiration, validation) ensures that even if individual tokens are compromised, the system remains secure through defense-in-depth principles.

The 60-day autonomous operation window supports real-world deployment scenarios (school holidays, weekends, maintenance periods) while the 15-minute access token expiration limits the attack window for stolen tokens to an acceptable level.

This architecture represents **industry best practices** and follows the same patterns used by major tech companies for device authentication and long-lived access scenarios.
