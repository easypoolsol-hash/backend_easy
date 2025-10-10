# 🔴 SECURITY ISSUE: API Key Hashing with SHA-256

**Date:** October 7, 2025
**Severity:** MEDIUM
**Status:** NEEDS FIX

---

## Problem

**Current code:** `kiosks/serializers.py` line 145

```python
# ❌ INSECURE: Using SHA-256 for API key hashing
api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
```

**Issues:**
1. ❌ No salt (same key = same hash)
2. ❌ Too fast (can brute force)
3. ❌ Vulnerable to rainbow tables
4. ❌ Not designed for credential storage

---

## Industry Standard: Use PBKDF2 or Argon2

### Option 1: Django's `make_password()` (RECOMMENDED) ✅

**Why:** Built-in, tested, includes salt, uses PBKDF2 by default

```python
# kiosks/serializers.py (Line 145)

# BEFORE (INSECURE):
import hashlib
api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

# AFTER (SECURE):
from django.contrib.auth.hashers import make_password, check_password

# When storing API key (during kiosk registration)
api_key_hash = make_password(api_key)
# Result: "pbkdf2_sha256$600000$salt$hash" (includes algorithm + iterations + salt + hash)

# When verifying API key (during authentication)
if check_password(api_key, stored_api_key_hash):
    # Authentication successful
```

**Benefits:**
- ✅ Uses PBKDF2 with 600,000 iterations (slow = secure)
- ✅ Includes random salt (prevents rainbow tables)
- ✅ Django maintains compatibility (auto-upgrades iterations)
- ✅ Same system used for user passwords

---

### Option 2: `secrets` module for API Key Generation ✅

**Current:** API keys might be predictable

```python
# If you're generating API keys, use this:
import secrets

# Generate cryptographically secure API key
api_key = secrets.token_urlsafe(32)
# Result: "8Jz4Y-x9K2mQ_r5WvLp3NcTg7HfB6DsA1eU0oI9j8Xw"

# Then hash it before storing
from django.contrib.auth.hashers import make_password
api_key_hash = make_password(api_key)
```

---

## Files to Update

### 1. Update API Key Hashing in Serializer

**File:** `backend_easy/app/kiosks/serializers.py`

**Current (Line 145):**
```python
import hashlib

class KioskAuthSerializer(serializers.Serializer):
    def validate(self, attrs):
        api_key = attrs.get('api_key')

        # ❌ INSECURE
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            kiosk = Kiosk.objects.get(
                kiosk_id=kiosk_id,
                api_key_hash=api_key_hash  # Exact match required
            )
```

**Fixed:**
```python
from django.contrib.auth.hashers import check_password

class KioskAuthSerializer(serializers.Serializer):
    def validate(self, attrs):
        api_key = attrs.get('api_key')

        # Get kiosk first
        try:
            kiosk = Kiosk.objects.get(kiosk_id=kiosk_id)
        except Kiosk.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')

        # ✅ SECURE: Use check_password to verify hashed API key
        if not check_password(api_key, kiosk.api_key_hash):
            raise serializers.ValidationError('Invalid credentials')

        # Verify kiosk is active
        if not kiosk.is_active:
            raise serializers.ValidationError('Kiosk is not active')
```

---

### 2. Update API Key Storage (When Creating Kiosk)

**File:** `backend_easy/app/kiosks/admin.py` or wherever kiosks are created

**Current (if exists):**
```python
import hashlib

# Creating new kiosk
api_key = "test-api-key-12345"  # Plain text
api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

kiosk = Kiosk.objects.create(
    kiosk_id="KIOSK001",
    api_key_hash=api_key_hash
)
```

**Fixed:**
```python
import secrets
from django.contrib.auth.hashers import make_password

# Generate secure API key
api_key = secrets.token_urlsafe(32)

# Hash it securely before storing
api_key_hash = make_password(api_key)

kiosk = Kiosk.objects.create(
    kiosk_id="KIOSK001",
    api_key_hash=api_key_hash
)

# IMPORTANT: Display api_key to user ONCE (cannot retrieve later)
print(f"API Key (save this): {api_key}")
```

---

### 3. Update Database Schema (If Needed)

**File:** `backend_easy/app/kiosks/models.py`

**Current:**
```python
api_key_hash = models.CharField(
    max_length=255,  # ✅ OK: Django hashes are ~120 chars
    unique=True,
    help_text="Hashed API key for device authentication"
)
```

**This is fine!** `max_length=255` is enough for Django's password hashes.

---

### 4. Migration Required

**Create migration to rehash existing API keys:**

```bash
python manage.py makemigrations --empty kiosks
```

**Edit migration:**
```python
from django.db import migrations
from django.contrib.auth.hashers import make_password
import hashlib

def rehash_api_keys(apps, schema_editor):
    """
    WARNING: This migration CANNOT run automatically!

    SHA-256 hashes are one-way. You CANNOT recover original API keys.

    Options:
    1. Regenerate API keys for all kiosks (recommended)
    2. Ask kiosks to re-register with new API keys
    3. Deploy new system, deprecate old kiosks
    """
    pass  # Manual intervention required

class Migration(migrations.Migration):
    dependencies = [
        ('kiosks', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(rehash_api_keys, migrations.RunPython.noop),
    ]
```

---

## Comparison: SHA-256 vs PBKDF2

| Feature | SHA-256 (Current) | PBKDF2 (Django) |
|---------|-------------------|-----------------|
| **Speed** | ~100M hashes/sec | ~1,000 hashes/sec |
| **Salt** | ❌ No | ✅ Yes (random) |
| **Rainbow Tables** | ❌ Vulnerable | ✅ Protected |
| **Brute Force** | ❌ Easy | ✅ Very difficult |
| **Same key → Same hash** | ❌ Yes | ✅ No (salt) |
| **Industry Standard** | ❌ For files only | ✅ For credentials |
| **Django Compatible** | ❌ No | ✅ Yes |

---

## Timeline for Fix

### Phase 1: Update Code (No Breaking Changes)
1. Update `serializers.py` to use `check_password()`
2. Update kiosk creation to use `make_password()`
3. Deploy to staging

### Phase 2: Migrate Existing Kiosks
**Problem:** Cannot recover original API keys from SHA-256 hashes

**Options:**
- **Option A (Clean):** Regenerate API keys for all kiosks
- **Option B (Gradual):** Support both hash types temporarily
- **Option C (Manual):** Ask admins to manually update each kiosk

### Phase 3: Remove Old Code
- Remove SHA-256 hashing code
- Update documentation

---

## Testing

### Test 1: New Kiosk Registration
```python
# Generate and store API key
api_key = secrets.token_urlsafe(32)
api_key_hash = make_password(api_key)

kiosk = Kiosk.objects.create(
    kiosk_id="TEST-KIOSK-001",
    api_key_hash=api_key_hash
)

# Verify authentication works
assert check_password(api_key, kiosk.api_key_hash)
assert not check_password("wrong-key", kiosk.api_key_hash)
```

### Test 2: Same Key → Different Hashes
```python
api_key = "same-key-12345"

hash1 = make_password(api_key)
hash2 = make_password(api_key)

# Should be different (due to random salt)
assert hash1 != hash2

# But both should verify correctly
assert check_password(api_key, hash1)
assert check_password(api_key, hash2)
```

---

## References

- [Django Password Hashers](https://docs.djangoproject.com/en/stable/topics/auth/passwords/)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [Python secrets module](https://docs.python.org/3/library/secrets.html)
- [Why not use SHA-256 for passwords](https://security.stackexchange.com/questions/211/how-to-securely-hash-passwords)

---

## Summary

**Current Usage:**
- ✅ `calculate_checksum()` for file integrity - CORRECT
- ❌ `hashlib.sha256()` for API keys - INCORRECT

**Required Fix:**
- Use `make_password()` and `check_password()` for API keys
- Use `secrets.token_urlsafe()` for generating API keys
- Keep `hashlib.sha256()` for snapshot checksums (that's fine!)

**Priority:** MEDIUM (not critical but should be fixed before production)
