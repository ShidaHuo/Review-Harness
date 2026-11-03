[CmdletBinding()]
param(
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $ProjectRoot "install.ps1"
$KeyFile = Join-Path $ProjectRoot "OPENALEX_API_KEY.txt"

Write-Host "=== Review Harness MVP - Codex Setup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"

& $Installer -Runtime codex

if (-not (Test-Path -LiteralPath $KeyFile -PathType Leaf)) {
    if ($NonInteractive) {
        throw "OPENALEX_API_KEY.txt is not configured. Run setup-codex.cmd interactively."
    }

    Write-Host ""
    Write-Host "An OpenAlex API key is required." -ForegroundColor Yellow
    Write-Host "The key is entered only in this local terminal. It is never sent to Codex chat or Git."
    $secureKey = Read-Host "Paste your own OpenAlex API key" -AsSecureString
    $credential = [System.Net.NetworkCredential]::new("", $secureKey)
    $plainKey = $credential.Password.Trim()

    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw "No OpenAlex API key was entered."
    }
    if ($plainKey.Contains("`r") -or $plainKey.Contains("`n")) {
        throw "The OpenAlex API key must contain exactly one line."
    }
    if ($plainKey.StartsWith("OPENALEX_API_KEY=")) {
        throw "Enter only the raw key, without the OPENALEX_API_KEY= prefix."
    }

    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($KeyFile, "$plainKey`n", $utf8WithoutBom)
    $plainKey = $null
    $credential = $null
    $secureKey = $null
    Write-Host "OpenAlex credential saved locally to OPENALEX_API_KEY.txt." -ForegroundColor Green
} else {
    Write-Host "OpenAlex credential file already exists; it was not read or overwritten." -ForegroundColor Green
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$keyStatus = & python -c "from review_harness.openalex import load_openalex_api_key; print('configured' if load_openalex_api_key() else 'not_configured')"
if ($LASTEXITCODE -ne 0 -or $keyStatus.Trim() -ne "configured") {
    throw "The Review Harness Python client could not load an OpenAlex API key."
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "1. Open this folder in Codex: $ProjectRoot"
Write-Host "2. Start a new Codex chat."
Write-Host "3. Enter a review request for your scientific topic."
Write-Host ""
Write-Host "Do not paste OpenAlex or institution credentials into Codex chat."
