@echo off
REM ============================================================================
REM Firebase Service Account Key Generator
REM ============================================================================
REM Project: easypool-30af3
REM Service Account: firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com
REM
REM This script generates a fresh Firebase Admin SDK service account key
REM and automatically backs up your existing key.
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo Firebase Service Account Key Generator
echo ========================================
echo Project: easypool-30af3
echo.

REM Check if gcloud CLI is installed
gcloud --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Google Cloud CLI is not installed.
    echo.
    echo Please install from: https://cloud.google.com/sdk/docs/install
    echo.
    echo ALTERNATIVE: Use Firebase Console
    echo 1. Go to: https://console.firebase.google.com/project/easypool-30af3/settings/serviceaccounts/adminsdk
    echo 2. Click "Generate New Private Key"
    echo 3. Save as: service-account-key.json in this folder
    echo.
    pause
    exit /b 1
)

REM Check if current key exists
if exist "service-account-key.json" (
    echo Found existing key - creating backup...

    REM Create backup with timestamp
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
    for /f "tokens=1-2 delims=/: " %%a in ('time /t') do (set mytime=%%a%%b)
    set timestamp=!mydate!-!mytime!

    copy "service-account-key.json" "service-account-key-backup-!timestamp!.json" >nul
    echo Backup saved: service-account-key-backup-!timestamp!.json
    echo.
) else (
    echo No existing key found - will create new key...
    echo.
)

echo Generating new service account key from Google Cloud...
echo.

REM Generate new service account key
gcloud iam service-accounts keys create service-account-key.json ^
    --iam-account=firebase-adminsdk-fbsvc@easypool-30af3.iam.gserviceaccount.com ^
    --project=easypool-30af3

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! New key generated.
    echo ========================================
    echo.
    echo Key saved to: service-account-key.json
    echo.
    echo IMPORTANT NEXT STEPS:
    echo.
    echo 1. RESTART your backend server to load the new key
    echo    - Stop current backend (Ctrl+C)
    echo    - Run: make backend
    echo.
    echo 2. Test authentication by logging into the app
    echo.
    echo 3. If authentication works, you can delete old backup files
    echo.
) else (
    echo.
    echo ========================================
    echo ERROR: Failed to generate key
    echo ========================================
    echo.
    echo Possible causes:
    echo 1. Not authenticated with gcloud (run: gcloud auth login)
    echo 2. No permission to create keys in this project
    echo 3. Service account was deleted or renamed
    echo.
    echo ALTERNATIVE METHOD:
    echo 1. Go to: https://console.firebase.google.com/project/easypool-30af3/settings/serviceaccounts/adminsdk
    echo 2. Click "Generate New Private Key"
    echo 3. Save as: service-account-key.json in this folder
    echo.
    echo If service account doesn't exist, list available ones:
    echo    gcloud iam service-accounts list --project=easypool-30af3
    echo.
)

pause
