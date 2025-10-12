# Install pre-commit hooks for Windows
# Run once after cloning repo

Write-Host "Installing pre-commit hooks..." -ForegroundColor Cyan

# Check if pre-commit is installed
try {
    pre-commit --version | Out-Null
} catch {
    Write-Host "pre-commit not found. Installing..." -ForegroundColor Yellow
    pip install pre-commit
}

# Install hooks
pre-commit install

# Install commit-msg hook (optional)
try {
    pre-commit install --hook-type commit-msg
} catch {
    # Ignore error if not needed
}

Write-Host "`n✅ Pre-commit hooks installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To test hooks without committing:" -ForegroundColor Yellow
Write-Host "  pre-commit run --all-files"
Write-Host ""
Write-Host "To skip hooks (not recommended):" -ForegroundColor Yellow
Write-Host "  git commit --no-verify"
