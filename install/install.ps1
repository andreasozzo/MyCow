#Requires -Version 5.1
<#
.SYNOPSIS
    MyCow Installer for Windows
.DESCRIPTION
    Installs MyCow in $HOME\MyCow, configures Python venv and registers the global 'mycow' command.
.EXAMPLE
    irm https://mycow.dev/install.ps1 | iex
#>

$ErrorActionPreference = "Stop"

$MYCOW_REPO_URL = "https://github.com/andreasozzo/MyCow/archive/refs/heads/master.zip"
$INSTALL_DIR    = Join-Path $HOME "MyCow"
$VENV_DIR       = Join-Path $INSTALL_DIR "venv"
$MIN_PYTHON     = [Version]"3.11"

# --- Helpers ------------------------------------------------------------

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   !   $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "`n[ERROR] $msg" -ForegroundColor Red; exit 1 }

# --- 1. Check Python -------------------------------------------------

Write-Step "Check Python 3.11+"

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+\.\d+)") {
            $found = [Version]$Matches[1]
            if ($found -ge $MIN_PYTHON) {
                $pythonCmd = $cmd
                Write-Ok "Found: $ver"
                break
            }
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Fail "Python 3.11+ not found. Download from https://python.org/downloads/"
}

# --- 2. Check Claude Code CLI ----------------------------------------

Write-Step "Check Claude Code CLI"

try {
    $claudeVer = & claude --version 2>&1
    Write-Ok "Found: $claudeVer"
} catch {
    Write-Warn "Claude Code CLI not found in PATH."
    Write-Warn "Install with: npm install -g @anthropic-ai/claude-code"
    Write-Warn "MyCow will be installed but won't work without Claude Code."
}

# --- 3. Download MyCow --------------------------------------------------

Write-Step "Download MyCow"

$freshInstall = $true
if (Test-Path $INSTALL_DIR) {
    Write-Warn "MyCow is already installed. Updating web files and dependencies..."
    $freshInstall = $false
}

$zipPath = Join-Path $env:TEMP "mycow.zip"
$extractPath = Join-Path $env:TEMP "mycow_extract"

Write-Host "   Downloading from $MYCOW_REPO_URL ..."
Invoke-WebRequest -Uri $MYCOW_REPO_URL -OutFile $zipPath -UseBasicParsing

if (Test-Path $extractPath) { Remove-Item $extractPath -Recurse -Force }
Expand-Archive -Path $zipPath -DestinationPath $extractPath

# GitHub zip extracts into a subfolder (e.g. mycow-main)
$innerDir = Get-ChildItem $extractPath | Where-Object { $_.PSIsContainer } | Select-Object -First 1

if ($freshInstall) {
    Move-Item $innerDir.FullName $INSTALL_DIR
    Write-Ok "Extracted to $INSTALL_DIR"
} else {
    # Update core files (daemon, web, install) but preserve config (agents, skills/global, .env)
    foreach ($dir in @("web", "daemon", "install")) {
        $srcPath = Join-Path $innerDir.FullName $dir
        $dstPath = Join-Path $INSTALL_DIR $dir
        if (Test-Path $srcPath) {
            if (Test-Path $dstPath) { Remove-Item $dstPath -Recurse -Force }
            Copy-Item -Path $srcPath -Destination $dstPath -Recurse -Force
        }
    }
    # Also update non-config files
    foreach ($file in @("README.md", "CLAUDE.md", "LICENSE", "requirements.txt", ".env.example")) {
        $srcFile = Join-Path $innerDir.FullName $file
        $dstFile = Join-Path $INSTALL_DIR $file
        if (Test-Path $srcFile) {
            Copy-Item -Path $srcFile -Destination $dstFile -Force
        }
    }
    Write-Ok "Updated core files (daemon, web, install, docs)"
}

Remove-Item $zipPath -Force
Remove-Item $extractPath -Recurse -Force

# --- 4. Create venv -------------------------------------------------------

Write-Step "Creating Python virtual environment"

if (-not (Test-Path $VENV_DIR)) {
    & $pythonCmd -m venv $VENV_DIR
    Write-Ok "venv created in $VENV_DIR"
} else {
    Write-Ok "venv already exists"
}

# --- 5. Install dependencies ---------------------------------------------

Write-Step "Installing Python dependencies"

$pip = Join-Path $VENV_DIR "Scripts\pip.exe"
$reqFile = Join-Path $INSTALL_DIR "requirements.txt"
if (-not (Test-Path $reqFile)) { Write-Fail "requirements.txt not found in $INSTALL_DIR. Broken install — remove $INSTALL_DIR and try again." }
& $pip install --upgrade pip --quiet
& $pip install -r $reqFile --quiet
Write-Ok "Dependencies installed"

# --- 6. Configure .env --------------------------------------------------

Write-Step "Configuring .env"

$envFile    = Join-Path $INSTALL_DIR ".env"
$envExample = Join-Path $INSTALL_DIR ".env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Ok ".env created from .env.example"
    } else {
        @"
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BRAVE_API_KEY=
MYCOW_PORT=3333
MYCOW_LOG_LEVEL=INFO
"@ | Set-Content $envFile -Encoding UTF8
        Write-Ok ".env created with default values"
    }
} else {
    Write-Ok ".env already exists (not overwritten)"
}

# --- 7. Remove dev skills -----------------------------------------------

Write-Step "Removing internal development skills"

foreach ($devSkill in @("ux-premium", "security-first")) {
    $skillPath = Join-Path $INSTALL_DIR "skills\global\$devSkill"
    if (Test-Path $skillPath) {
        Remove-Item $skillPath -Recurse -Force
        Write-Ok "Removed: $devSkill"
    }
}

# --- 8. Create mycow.bat --------------------------------------------------

Write-Step "Creating 'mycow' command"

$batPath = Join-Path $INSTALL_DIR "mycow.bat"
@"
@echo off
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0daemon\main.py" %*
"@ | Set-Content $batPath -Encoding ASCII
Write-Ok "Created: $batPath"

# --- 9. Add to PATH ------------------------------------------------

Write-Step "Registering in user PATH"

$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$INSTALL_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$INSTALL_DIR;$userPath", "User")
    Write-Ok "Added to user PATH"
    Write-Warn "Reopen terminal to use 'mycow' from any directory"
} else {
    Write-Ok "Already in PATH"
}

# --- Fine ---------------------------------------------------------------

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  MyCow installed successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Start daemon:       mycow start"
Write-Host "  Stop daemon:        mycow stop"
Write-Host "  Status:             mycow status"
Write-Host ""
Write-Host "  Configure your secrets in: $envFile"
Write-Host "  Or open Web UI:             http://127.0.0.1:3333 → Settings"
Write-Host ""
