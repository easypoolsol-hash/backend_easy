# Update SDK version in frontend_easy_api pubspec.yaml
$pubspecPath = "../frontend_easy/packages/frontend_easy_api/pubspec.yaml"
$content = Get-Content $pubspecPath -Raw
$updatedContent = $content -replace "sdk: '>=\d+\.\d+\.\d+ <\d+\.\d+\.\d+'", "sdk: '>=3.9.0 <4.0.0'"
Set-Content -Path $pubspecPath -Value $updatedContent -NoNewline
Write-Host "Updated SDK version to >=3.9.0 <4.0.0"
