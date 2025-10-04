# Local Security Scanning Script for Windows
# This script runs Trivy security scanning on your Docker image

Write-Host "Starting local security scan..." -ForegroundColor Cyan

# Configuration
$IMAGE_NAME = "bus_kiosk_backend"
$IMAGE_TAG = "test"
$FULL_IMAGE = "${IMAGE_NAME}:${IMAGE_TAG}"

# Check if Docker is running
Write-Host ""
Write-Host "Checking Docker..." -ForegroundColor Yellow
docker --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not installed or not running" -ForegroundColor Red
    exit 1
}

# Check if image exists
Write-Host ""
Write-Host "Checking if Docker image exists..." -ForegroundColor Yellow
docker images $FULL_IMAGE --format "{{.Repository}}:{{.Tag}}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Image $FULL_IMAGE not found. Please build it first with:" -ForegroundColor Red
    Write-Host "   docker build -t ${FULL_IMAGE} ." -ForegroundColor Yellow
    exit 1
}

# Check if Trivy is installed
Write-Host ""
Write-Host "Checking Trivy installation..." -ForegroundColor Yellow
$trivyInstalled = $false
try {
    $null = Get-Command trivy -ErrorAction Stop
    $trivyInstalled = $true
    Write-Host "Trivy is installed locally" -ForegroundColor Green
} catch {
    Write-Host "Trivy not found. Will use Docker to run Trivy..." -ForegroundColor Yellow
}

if (-not $trivyInstalled) {
    # Run Trivy in Docker container
    Write-Host ""
    Write-Host "Running Trivy via Docker container..." -ForegroundColor Cyan

    Write-Host ""
    Write-Host "Scanning image for vulnerabilities (Table format)..." -ForegroundColor Cyan
    docker run --rm `
        -v /var/run/docker.sock:/var/run/docker.sock `
        -v ${PWD}:/output `
        aquasec/trivy:latest image `
        --format table `
        --severity HIGH,CRITICAL `
        $FULL_IMAGE

    Write-Host ""
    Write-Host "Generating SARIF report..." -ForegroundColor Cyan
    docker run --rm `
        -v /var/run/docker.sock:/var/run/docker.sock `
        -v ${PWD}:/output `
        aquasec/trivy:latest image `
        --format sarif `
        --output /output/trivy-results.sarif `
        $FULL_IMAGE

    Write-Host ""
    Write-Host "Generating JSON report..." -ForegroundColor Cyan
    docker run --rm `
        -v /var/run/docker.sock:/var/run/docker.sock `
        -v ${PWD}:/output `
        aquasec/trivy:latest image `
        --format json `
        --output /output/trivy-results.json `
        $FULL_IMAGE
} else {
    # Run Trivy locally
    Write-Host ""
    Write-Host "Scanning image for vulnerabilities (Table format)..." -ForegroundColor Cyan
    trivy image --severity HIGH,CRITICAL $FULL_IMAGE

    Write-Host ""
    Write-Host "Generating SARIF report..." -ForegroundColor Cyan
    trivy image --format sarif --output trivy-results.sarif $FULL_IMAGE

    Write-Host ""
    Write-Host "Generating JSON report..." -ForegroundColor Cyan
    trivy image --format json --output trivy-results.json $FULL_IMAGE
}

if (Test-Path "trivy-results.sarif") {
    Write-Host ""
    Write-Host "Security scan complete!" -ForegroundColor Green
    Write-Host "Reports generated:" -ForegroundColor Cyan
    Write-Host "   - trivy-results.sarif (for CodeQL/GitHub)" -ForegroundColor White
    Write-Host "   - trivy-results.json (detailed JSON)" -ForegroundColor White
    Write-Host ""
    Write-Host "To view SARIF in VS Code, install the SARIF Viewer extension" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "SARIF file not generated" -ForegroundColor Yellow
}
