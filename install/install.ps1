#Requires -Version 5.1
<#
.SYNOPSIS
    MyCow Installer per Windows
.DESCRIPTION
    Installa MyCow in $HOME\MyCow, configura il venv Python e registra il comando globale 'mycow'.
.EXAMPLE
    irm https://mycow.dev/install.ps1 | iex
#>

$ErrorActionPreference = "Stop"

$MYCOW_REPO_URL = "https://github.com/andreasozzo/MyCow/archive/refs/heads/main.zip"
$INSTALL_DIR    = Join-Path $HOME "MyCow"
$VENV_DIR       = Join-Path $INSTALL_DIR "venv"
$MIN_PYTHON     = [Version]"3.11"

# --- Helpers ------------------------------------------------------------

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   !   $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "`n[ERRORE] $msg" -ForegroundColor Red; exit 1 }

# --- 1. Verifica Python -------------------------------------------------

Write-Step "Verifica Python 3.11+"

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+\.\d+)") {
            $found = [Version]$Matches[1]
            if ($found -ge $MIN_PYTHON) {
                $pythonCmd = $cmd
                Write-Ok "Trovato: $ver"
                break
            }
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Fail "Python 3.11+ non trovato. Scarica da https://python.org/downloads/"
}

# --- 2. Verifica Claude Code CLI ----------------------------------------

Write-Step "Verifica Claude Code CLI"

try {
    $claudeVer = & claude --version 2>&1
    Write-Ok "Trovato: $claudeVer"
} catch {
    Write-Warn "Claude Code CLI non trovato nel PATH."
    Write-Warn "Installa con: npm install -g @anthropic-ai/claude-code"
    Write-Warn "MyCow verra' installato ma non funzionera' senza Claude Code."
}

# --- 3. Download MyCow --------------------------------------------------

Write-Step "Download MyCow"

if (Test-Path $INSTALL_DIR) {
    Write-Warn "Cartella $INSTALL_DIR gia' esistente. Aggiorno solo le dipendenze."
} else {
    $zipPath = Join-Path $env:TEMP "mycow.zip"
    $extractPath = Join-Path $env:TEMP "mycow_extract"

    Write-Host "   Scarico da $MYCOW_REPO_URL ..."
    Invoke-WebRequest -Uri $MYCOW_REPO_URL -OutFile $zipPath -UseBasicParsing

    if (Test-Path $extractPath) { Remove-Item $extractPath -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $extractPath

    # La zip di GitHub estrae in una sottocartella (es. mycow-main)
    $innerDir = Get-ChildItem $extractPath | Where-Object { $_.PSIsContainer } | Select-Object -First 1
    Move-Item $innerDir.FullName $INSTALL_DIR

    Remove-Item $zipPath -Force
    Remove-Item $extractPath -Recurse -Force
    Write-Ok "Estratto in $INSTALL_DIR"
}

# --- 4. Crea venv -------------------------------------------------------

Write-Step "Creazione ambiente virtuale Python"

if (-not (Test-Path $VENV_DIR)) {
    & $pythonCmd -m venv $VENV_DIR
    Write-Ok "Venv creato in $VENV_DIR"
} else {
    Write-Ok "Venv gia' esistente"
}

# --- 5. Installa dipendenze ---------------------------------------------

Write-Step "Installazione dipendenze Python"

$pip = Join-Path $VENV_DIR "Scripts\pip.exe"
$reqFile = Join-Path $INSTALL_DIR "requirements.txt"
& $pip install --upgrade pip --quiet
& $pip install -r $reqFile --quiet
Write-Ok "Dipendenze installate"

# --- 6. Configura .env --------------------------------------------------

Write-Step "Configurazione .env"

$envFile    = Join-Path $INSTALL_DIR ".env"
$envExample = Join-Path $INSTALL_DIR ".env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Ok ".env creato da .env.example"
    } else {
        @"
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BRAVE_API_KEY=
MYCOW_PORT=3333
MYCOW_LOG_LEVEL=INFO
"@ | Set-Content $envFile -Encoding UTF8
        Write-Ok ".env creato con valori di default"
    }
} else {
    Write-Ok ".env gia' esistente (non sovrascritto)"
}

# --- 7. Rimuovi skill dev -----------------------------------------------

Write-Step "Rimozione skill di sviluppo interno"

foreach ($devSkill in @("ux-premium", "security-first")) {
    $skillPath = Join-Path $INSTALL_DIR "skills\global\$devSkill"
    if (Test-Path $skillPath) {
        Remove-Item $skillPath -Recurse -Force
        Write-Ok "Rimossa: $devSkill"
    }
}

# --- 8. Crea mycow.bat --------------------------------------------------

Write-Step "Creazione comando 'mycow'"

$batPath = Join-Path $INSTALL_DIR "mycow.bat"
@"
@echo off
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0daemon\main.py" %*
"@ | Set-Content $batPath -Encoding ASCII
Write-Ok "Creato: $batPath"

# --- 9. Aggiunge al PATH ------------------------------------------------

Write-Step "Registrazione nel PATH utente"

$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$INSTALL_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$INSTALL_DIR;$userPath", "User")
    Write-Ok "Aggiunto al PATH utente"
    Write-Warn "Riapri il terminale per usare 'mycow' da qualsiasi directory"
} else {
    Write-Ok "Gia' nel PATH"
}

# --- Fine ---------------------------------------------------------------

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  MyCow installato con successo!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Avvia il daemon:    mycow start"
Write-Host "  Ferma il daemon:    mycow stop"
Write-Host "  Stato:              mycow status"
Write-Host ""
Write-Host "  Configura i tuoi secrets in: $envFile"
Write-Host "  Oppure aprendo la Web UI:    http://127.0.0.1:3333 → Settings"
Write-Host ""
