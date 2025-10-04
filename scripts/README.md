# Scripts Directory

This directory contains utility scripts for local development and testing.

## Security Scanning

### `security-scan.ps1` (Windows PowerShell)
Runs Trivy security scanning on your Docker image locally.

**Usage:**
```powershell
.\scripts\security-scan.ps1
```

**Prerequisites:**
- Docker must be running
- Docker image `bus_kiosk_backend:test` must be built

**What it does:**
1. Checks if Docker is installed and running
2. Verifies the Docker image exists
3. Runs Trivy vulnerability scanner (via Docker if Trivy is not installed locally)
4. Generates three types of reports:
   - Console table output (HIGH and CRITICAL vulnerabilities only)
   - SARIF report (`trivy-results.sarif`) - compatible with GitHub Code Scanning
   - JSON report (`trivy-results.json`) - detailed vulnerability data

**Viewing SARIF results:**
- Install the [SARIF Viewer](https://marketplace.visualstudio.com/items?itemName=MS-SarifVSCode.sarif-viewer) extension in VS Code
- Open the `trivy-results.sarif` file in VS Code

### `security-scan.sh` (Linux/Mac Bash)
Same functionality as the PowerShell version, but for Unix-based systems.

**Usage:**
```bash
chmod +x scripts/security-scan.sh
./scripts/security-scan.sh
```

## CI Testing

### `ci-test.sh`
Runs the full test suite as it would run in CI/CD pipeline.

**Usage:**
```bash
chmod +x scripts/ci-test.sh
./scripts/ci-test.sh
```

**What it does:**
1. Runs Django migrations
2. Collects static files
3. Executes pytest with coverage

## Notes

- All generated reports (`.sarif`, `.json`) are automatically excluded from version control via `.gitignore`
- The security scan scripts will automatically use Docker to run Trivy if it's not installed locally
- For CI/CD, SARIF upload is commented out in `.github/workflows/ci.yml` to run locally instead
