@echo off
REM Generate Firebase service account key
REM Project: easypool-30af3

echo ========================================
echo Firebase Service Account Key Generator
echo ========================================
echo.
echo This will generate a service account key for your Firebase project.
echo The key will be saved to: firebase_keys\service-account-key.json
echo.

REM Check if gcloud CLI is installed
gcloud --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Google Cloud CLI is not installed.
    echo.
    echo Please install it from: https://cloud.google.com/sdk/docs/install
    echo.
    echo OR use Firebase Console:
    echo 1. Go to: https://console.firebase.google.com/project/easypool-30af3/settings/serviceaccounts/adminsdk
    echo 2. Click "Generate New Private Key"
    echo 3. Save to: backend_easy\firebase_keys\service-account-key.json
    echo.
    pause
    exit /b 1
)

echo Generating service account key...
echo.

REM Generate service account key
gcloud iam service-accounts keys create firebase_keys\service-account-key.json ^
    --iam-account=firebase-adminsdk-7xnux@easypool-30af3.iam.gserviceaccount.com ^
    --project=easypool-30af3

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Key generated successfully.
    echo ========================================
    echo.
    echo Key saved to: firebase_keys\service-account-key.json
    echo.
    echo Next steps:
    echo 1. Update .env file with: FIREBASE_SERVICE_ACCOUNT_KEY_PATH=firebase_keys/service-account-key.json
    echo 2. Keep this key secure - it's gitignored
    echo.
) else (
    echo.
    echo ========================================
    echo ALTERNATIVE METHOD
    echo ========================================
    echo.
    echo Use Firebase Console:
    echo 1. Go to: https://console.firebase.google.com/project/easypool-30af3/settings/serviceaccounts/adminsdk
    echo 2. Click "Generate New Private Key"
    echo 3. Save to: backend_easy\firebase_keys\service-account-key.json
    echo.
)

pause
