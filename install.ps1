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

if ($Runtime -eq "codex") {
    $codexSkillSource = Join-Path $ProjectRoot "codex-skill\review-harness"
    if (-not (Test-Path -LiteralPath $codexSkillSource -PathType Container)) {
        throw "Bundled Codex Skill was not found: $codexSkillSource"
    }

    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    $codexSkillsRoot = Join-Path $codexHome "skills"
    $codexSkillDestination = Join-Path $codexSkillsRoot "review-harness"
    $managedMarker = Join-Path $codexSkillDestination ".review-harness-managed"

    New-Item -ItemType Directory -Path $codexSkillsRoot -Force | Out-Null
    if (Test-Path -LiteralPath $codexSkillDestination -PathType Container) {
        if (-not (Test-Path -LiteralPath $managedMarker -PathType Leaf)) {
            throw "Refusing to overwrite an unmanaged Codex Skill: $codexSkillDestination"
        }
        Get-ChildItem -LiteralPath $codexSkillSource -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $codexSkillDestination $_.Name) -Recurse -Force
        }
    } else {
        Copy-Item -LiteralPath $codexSkillSource -Destination $codexSkillDestination -Recurse
    }
    $projectRootPointer = Join-Path $codexSkillDestination "project-root.txt"
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($projectRootPointer, "$ProjectRoot`n", $utf8WithoutBom)
    Write-Host "Installed global Codex Skill: $codexSkillDestination"
}

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

if ($Runtime -eq "codex") {
    Write-Host "Installation complete. Restart Codex, then invoke `$review-harness from any workspace."
} else {
    Write-Host "Installation complete. Open this repository as the workspace in your supported agent host."
}
