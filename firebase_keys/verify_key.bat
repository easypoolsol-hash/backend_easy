@echo off
REM ============================================================================
REM Firebase Service Account Key Verification
REM ============================================================================
REM This script verifies your current Firebase key and shows active keys
REM ============================================================================

echo.
echo ========================================
echo Firebase Key Verification
echo ========================================
echo.

REM Check if key file exists
if not exist "service-account-key.json" (
    echo ERROR: service-account-key.json not found!
    echo.
    echo Run get_new_firebase_key.bat to generate a key.
    echo.
    pause
    exit /b 1
)

echo Checking local key file...
echo.

REM Verify key using Python
python -c "import json; key=json.load(open('service-account-key.json')); print('Local Key File:'); print('  Project:', key['project_id']); print('  Service Account:', key['client_email']); print('  Key ID:', key['private_key_id'][:16] + '...')"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Could not read service-account-key.json
    echo The file may be corrupted.
    echo.
    pause
    exit /b 1
)

echo.
echo ----------------------------------------
echo.

REM Check if gcloud is installed
gcloud --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Google Cloud CLI not installed
    echo Cannot verify active keys in Google Cloud
    echo.
    echo Local key file looks valid.
    echo.
    pause
    exit /b 0
)

echo Checking active keys in Google Cloud...
echo.

REM List active keys
gcloud iam service-accounts keys list ^
    --iam-account=firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com ^
    --project=easypool-30af3 ^
    --filter="keyType=USER_MANAGED" ^
    --format="table(name.basename():label='KEY_ID',validAfterTime.date():label='CREATED')"

echo.
echo ========================================
echo Verification Complete
echo ========================================
echo.
echo Security Recommendation:
echo - Keep only 1-2 active keys
echo - Delete old keys after testing new ones
echo - Rotate keys every 90 days
echo.

pause
