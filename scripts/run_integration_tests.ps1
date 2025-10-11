# Run integration/performance tests using docker-compose.test.yml
# Usage: .\run_integration_tests.ps1 -ComposeFile ..\docker-compose.test.yml -PytestArgs "-q --maxfail=1 --disable-warnings --cov=app"
param(
    [string]$ComposeFile = "..\docker-compose.test.yml",
    [string]$ProjectName = "backend_easy_test",
    [string]$PytestArgs = "-q --maxfail=1 --disable-warnings --cov=app",
    [int]$DbWaitSeconds = 60
)

Write-Host "Starting test infrastructure using $ComposeFile"
Push-Location (Split-Path -Path $ComposeFile -Parent)

# Start services in detached mode
docker compose -f $ComposeFile --project-directory . up -d --build

# Helper: wait for a TCP port to be open on localhost
function Wait-ForPort($hostname, $port, $timeoutSeconds) {
    $end = [DateTime]::UtcNow.AddSeconds($timeoutSeconds)
    while ([DateTime]::UtcNow -lt $end) {
        try {
            $sock = New-Object System.Net.Sockets.TcpClient
            $async = $sock.BeginConnect($hostname, $port, $null, $null)
            $wait = $async.AsyncWaitHandle.WaitOne(1000)
            if ($wait -and $sock.Connected) {
                $sock.Close()
                return $true
            }
        } catch {
            # ignore and retry
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

Write-Host "Waiting for Postgres (localhost:5432) to be ready..."
if (-not (Wait-ForPort -hostname 'localhost' -port 5432 -timeoutSeconds $DbWaitSeconds)) {
    Write-Error "Postgres did not become available within $DbWaitSeconds seconds"
    docker compose -f $ComposeFile down
    exit 1
}

Write-Host "Waiting for Redis (localhost:6379) to be ready..."
if (-not (Wait-ForPort -hostname 'localhost' -port 6379 -timeoutSeconds 30)) {
    Write-Error "Redis did not become available in time"
    docker compose -f $ComposeFile down
    exit 1
}

# Export environment variables expected by Django test runner
$env:DB_ENGINE = 'django.db.backends.postgresql'
$env:DB_NAME = 'test_db'
$env:DB_USER = 'postgres'
$env:DB_PASSWORD = 'postgres'
$env:DB_HOST = 'localhost'
$env:DB_PORT = '5432'
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:CI = 'true'
$env:SECRET_KEY = 'test-secret-key-for-testing-only'

# Run migrations to prepare the test DB (if necessary)
Write-Host "Applying migrations (inside host Django test environment)"
# Use local python environment to run manage.py migrate
python -m pip install -r ..\requirements.txt 2>$null | Out-Null
python ..\app\manage.py migrate --noinput

# Run pytest (host runner) pointing to test DB
Write-Host "Running pytest with args: $PytestArgs"
$pytestCmd = "python -m pytest $PytestArgs"
Write-Host $pytestCmd
Invoke-Expression $pytestCmd
$pytestExit = $LASTEXITCODE

Write-Host "Tearing down test infrastructure"
docker compose -f $ComposeFile down -v

Pop-Location
exit $pytestExit
