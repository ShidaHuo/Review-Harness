[CmdletBinding()]
param(
    [ValidateSet("auto", "deepseek-harness", "kiro-crew", "codex")]
    [string]$Runtime = "auto",
    [switch]$InstallDeepSeekPlugin,
    [string]$DshProfile = "desktop",
    [string]$DshCliPath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw "Python 3.12 or newer is required and was not found on PATH."
}

$versionText = & $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$versionParts = $versionText.Split('.')
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 12)) {
    throw "Python 3.12 or newer is required; found $versionText."
}

Write-Host "Installing Review Harness in editable mode from $ProjectRoot"
& $pythonCommand.Source -m pip install -e $ProjectRoot

$adapterArgs = @((Join-Path $ProjectRoot "runtime_adapter.py"), "--compact")
if ($Runtime -ne "auto") {
    $adapterArgs += @("--runtime", $Runtime)
}
& $pythonCommand.Source @adapterArgs

if ($InstallDeepSeekPlugin) {
    $dsh = $null
    if ($DshCliPath) {
        if (-not (Test-Path -LiteralPath $DshCliPath -PathType Leaf)) {
            throw "The supplied DeepSeek Harness CLI path does not exist: $DshCliPath"
        }
        $dsh = (Resolve-Path -LiteralPath $DshCliPath).Path
    } else {
        $dshCommand = Get-Command dsh -ErrorAction SilentlyContinue
        if ($dshCommand) {
            $dsh = $dshCommand.Source
        }
    }
    if (-not $dsh) {
        throw "DeepSeek Harness CLI was not found. Re-run with -DshCliPath pointing to dsh or dsh.cmd."
    }
    $pluginPath = Join-Path $ProjectRoot "plugin\perspective-branches"
    & $dsh plugin --profile $DshProfile add "file:$pluginPath"
    Write-Host "Installed the persistent perspective Session-fork plugin into profile '$DshProfile'."
}

$keyFile = Join-Path $ProjectRoot "OPENALEX_API_KEY.txt"
if (Test-Path -LiteralPath $keyFile -PathType Leaf) {
    Write-Host "OpenAlex credential status: configured"
} else {
    Write-Host "OpenAlex credential status: not configured"
    Write-Host "Create OPENALEX_API_KEY.txt with one line containing your own key, or set OPENALEX_API_KEY."
}

Write-Host "Installation complete. Open this repository as the workspace in your supported agent host."
