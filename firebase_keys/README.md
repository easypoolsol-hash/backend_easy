# Firebase Service Account Key

This folder contains the Firebase Admin SDK service account key used for backend authentication.

## Current Configuration

- **Firebase Project:** `easypool-30af3`
- **Service Account:** `firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com`
- **Key File:** `service-account-key.json` (gitignored)
- **Last Key Generated:** 2025-10-30
- **Active Keys:** 1 user-managed key (recommended: keep only 1-2)

## When to Generate a New Key

Generate a new Firebase service account key when:
- Authentication fails with "Invalid Firebase token" errors
- Key is compromised or exposed
- Key expires (keys don't expire but can be revoked)
- Rotating credentials for security (recommended every 90 days)

## How to Generate a New Key

### Option 1: Using Batch File (Recommended)
```cmd
get_new_firebase_key.bat
```

This will:
1. Backup your current key to `service-account-key-backup-YYYYMMDD-HHMMSS.json`
2. Generate a fresh key from Google Cloud
3. Save it as `service-account-key.json`
4. Remind you to restart the backend

### Option 2: Using Firebase Console (Manual)
1. Go to [Firebase Console - Service Accounts](https://console.firebase.google.com/project/easypool-30af3/settings/serviceaccounts/adminsdk)
2. Click "Generate New Private Key"
3. Save the downloaded file as `service-account-key.json` in this folder

### Option 3: Using gcloud CLI (Manual)
```cmd
gcloud iam service-accounts keys create service-account-key.json ^
    --iam-account=firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com ^
    --project=easypool-30af3
```

## After Generating a New Key

**IMPORTANT:** Restart your backend server to load the new key:
```cmd
cd ..
# Stop current backend (Ctrl+C)
make backend
```

## Security Notes

- This key is **sensitive** - never commit to git (already in .gitignore)
- Grants full admin access to Firebase project
- Keep backups secure
- Rotate keys every 90 days for best security
- **Delete old keys** after generating new ones to minimize security risk

### Managing Multiple Keys

When you generate a new key, the old keys remain active until deleted. To view all active keys:

```cmd
gcloud iam service-accounts keys list ^
    --iam-account=firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com ^
    --project=easypool-30af3
```

To delete an old key (after confirming new key works):

```cmd
gcloud iam service-accounts keys delete KEY_ID ^
    --iam-account=firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com ^
    --project=easypool-30af3
```

**Best Practice:** Keep only 1-2 active keys at a time (current + optional backup)

## Troubleshooting

**Error: "Invalid Firebase token"**
- Generate a new key using the batch file
- Restart the backend
- Clear frontend cache and re-login

**Error: "Service account not found"**
- The service account email may have changed in Firebase Console
- Update the batch file with the new service account email
- List service accounts: `gcloud iam service-accounts list --project=easypool-30af3`

## Verification

To verify your current key and see all active keys:

```cmd
verify_key.bat
```

This will show:
- Local key file information
- All active keys in Google Cloud
- Security recommendations

## File Structure

```text
firebase_keys/
├── README.md                           # This file
├── get_new_firebase_key.bat           # Automated key generation script
├── verify_key.bat                     # Verify current key status
├── service-account-key.json           # Current active key (gitignored)
├── service-account-key-backup-*.json  # Automatic backups (gitignored)
└── .gitignore                         # Ensures keys never committed
```
