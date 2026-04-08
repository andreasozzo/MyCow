#!/usr/bin/env bash
# MyCow Installer for Mac/Linux
# Usage: curl -fsSL https://mycow.dev/install.sh | bash

set -euo pipefail

MYCOW_REPO_URL="https://github.com/andreasozzo/MyCow/archive/refs/heads/master.zip"
INSTALL_DIR="$HOME/MyCow"
VENV_DIR="$INSTALL_DIR/venv"
MIN_PYTHON_MINOR=11  # 3.11+

# --- Helpers ------------------------------------------------------------

step()  { echo ""; echo ">> $1"; }
ok()    { echo "   OK  $1"; }
warn()  { echo "   !   $1"; }
fail()  { echo ""; echo "[ERROR] $1" >&2; exit 1; }

# Colors (only in interactive terminal)
if [ -t 1 ]; then
    step()  { echo ""; echo -e "\033[36m>> $1\033[0m"; }
    ok()    { echo -e "   \033[32mOK\033[0m  $1"; }
    warn()  { echo -e "   \033[33m!\033[0m   $1"; }
    fail()  { echo -e "\n\033[31m[ERROR] $1\033[0m" >&2; exit 1; }
fi

# --- 1. Check Python -------------------------------------------------

step "Check Python 3.11+"

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge $MIN_PYTHON_MINOR ]; then
            PYTHON_CMD="$cmd"
            ok "Found: $cmd $ver"
            break
        fi
    fi
done

[ -z "$PYTHON_CMD" ] && fail "Python 3.11+ not found. Download from https://python.org/downloads/"

# --- 2. Check Claude Code CLI ----------------------------------------

step "Check Claude Code CLI"

if command -v claude &>/dev/null; then
    ok "Found: $(claude --version 2>&1 | head -1)"
else
    warn "Claude Code CLI not found in PATH."
    warn "Install with: npm install -g @anthropic-ai/claude-code"
    warn "MyCow will be installed but won't work without Claude Code."
fi

# --- 3. Download MyCow --------------------------------------------------

step "Download MyCow"

# Check that unzip is available
if ! command -v unzip &>/dev/null; then
    warn "unzip not found. Installing..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y unzip --quiet || fail "Failed to install unzip."
    elif command -v brew &>/dev/null; then
        brew install unzip --quiet || fail "Failed to install unzip."
    else
        fail "unzip not found. Install it with your distro's package manager."
    fi
fi

FRESH_INSTALL=true
UPDATE_WEB_FILES=false

if [ -d "$INSTALL_DIR" ]; then
    # If folder exists but requirements.txt is missing, it's a broken install
    if [ ! -f "$INSTALL_DIR/requirements.txt" ]; then
        warn "Broken install found. Removing and re-downloading..."
        rm -rf "$INSTALL_DIR"
    else
        FRESH_INSTALL=false
        warn "MyCow is already installed. Updating web files and dependencies..."
        UPDATE_WEB_FILES=true
    fi
fi

TMP_ZIP=$(mktemp /tmp/mycow_XXXXXX.zip)
TMP_EXTRACT=$(mktemp -d /tmp/mycow_extract_XXXXXX)

echo "   Downloading from $MYCOW_REPO_URL ..."
if command -v curl &>/dev/null; then
    curl -fsSL "$MYCOW_REPO_URL" -o "$TMP_ZIP"
elif command -v wget &>/dev/null; then
    wget -q "$MYCOW_REPO_URL" -O "$TMP_ZIP"
else
    fail "curl or wget required for download."
fi

unzip -q "$TMP_ZIP" -d "$TMP_EXTRACT"

# GitHub zip extracts into a subfolder (e.g. MyCow-master)
INNER_DIR=$(find "$TMP_EXTRACT" -maxdepth 1 -mindepth 1 -type d | head -1)

if [ "$FRESH_INSTALL" = true ]; then
    mv "$INNER_DIR" "$INSTALL_DIR"
    ok "Extracted to $INSTALL_DIR"
else
    # Update web files
    if [ -d "$INNER_DIR/web" ]; then
        cp -r "$INNER_DIR/web"/* "$INSTALL_DIR/web/" 2>/dev/null || true
        ok "Updated web files"
    fi
fi

rm -f "$TMP_ZIP"
rm -rf "$TMP_EXTRACT"

# --- 4. Create venv -------------------------------------------------------

step "Creating Python virtual environment"

if [ -d "$VENV_DIR" ] && [ ! -f "$VENV_DIR/bin/pip" ]; then
    warn "Broken venv found. Removing and recreating..."
    rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
    # Check FIRST if venv module is available (Debian/Ubuntu doesn't include it by default)
    if ! "$PYTHON_CMD" -c "import ensurepip" 2>/dev/null; then
        PYTHON_VER=$("$PYTHON_CMD" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        warn "venv module not available. Installing python${PYTHON_VER}-venv (requires sudo password)..."
        if command -v apt-get &>/dev/null; then
            sudo apt-get install -y "python${PYTHON_VER}-venv" --quiet \
                || fail "Failed to install python${PYTHON_VER}-venv. Run: sudo apt install python${PYTHON_VER}-venv"
        else
            fail "Install python3-venv for your distro and try again."
        fi
    fi
    "$PYTHON_CMD" -m venv "$VENV_DIR" || fail "venv creation failed."
    ok "venv created in $VENV_DIR"
else
    ok "venv already exists"
fi

# --- 5. Install dependencies ---------------------------------------------

step "Installing Python dependencies"

[ ! -f "$INSTALL_DIR/requirements.txt" ] && fail "requirements.txt not found. Broken install — remove $INSTALL_DIR and try again."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
ok "Dependencies installed"

# --- 6. Configure .env --------------------------------------------------

step "Configuring .env"

ENV_FILE="$INSTALL_DIR/.env"
ENV_EXAMPLE="$INSTALL_DIR/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        ok ".env created from .env.example"
    else
        cat > "$ENV_FILE" <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BRAVE_API_KEY=
MYCOW_PORT=3333
MYCOW_LOG_LEVEL=INFO
EOF
        ok ".env created with default values"
    fi
else
    ok ".env already exists (not overwritten)"
fi

# --- 7. Remove dev skills -----------------------------------------------

step "Removing internal development skills"

for skill in ux-premium security-first; do
    skill_path="$INSTALL_DIR/skills/global/$skill"
    if [ -d "$skill_path" ]; then
        rm -rf "$skill_path"
        ok "Removed: $skill"
    fi
done

# --- 8. Create 'mycow' wrapper script ------------------------------------

step "Creating 'mycow' command"

WRAPPER="$INSTALL_DIR/mycow"
cat > "$WRAPPER" <<'WRAPPER_EOF'
#!/usr/bin/env bash
# Resolve symlink to find MyCow's actual directory
SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || realpath "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/daemon/main.py" "$@"
WRAPPER_EOF
chmod +x "$WRAPPER"
ok "Created: $WRAPPER"

# --- 9. Register in PATH -----------------------------------------------

step "Registering in PATH"

LINKED=false

# Try symlink in /usr/local/bin (requires permissions)
if [ -w "/usr/local/bin" ] || sudo -n true 2>/dev/null; then
    # Remove any previous version (file or old symlink)
    sudo rm -f /usr/local/bin/mycow 2>/dev/null
    if sudo ln -sf "$WRAPPER" /usr/local/bin/mycow 2>/dev/null; then
        ok "Symlink created: /usr/local/bin/mycow"
        LINKED=true
    fi
fi

if [ "$LINKED" = false ]; then
    # Fallback: add to PATH in .bashrc and .zshrc
    EXPORT_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""
    for rc_file in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$rc_file" ] && ! grep -qF "$INSTALL_DIR" "$rc_file"; then
            echo "" >> "$rc_file"
            echo "# MyCow" >> "$rc_file"
            echo "$EXPORT_LINE" >> "$rc_file"
            ok "Added PATH to $rc_file"
        fi
    done
    warn "Reopen terminal (or run: source ~/.bashrc) to use 'mycow'"
fi

# --- Fine ---------------------------------------------------------------

echo ""
echo "=========================================="
echo "  MyCow installed successfully!"
echo "=========================================="
echo ""
echo "  Start daemon:       mycow start"
echo "  Stop daemon:        mycow stop"
echo "  Status:             mycow status"
echo ""
echo "  Configure your secrets in: $ENV_FILE"
echo "  Or open Web UI:             http://127.0.0.1:3333 → Settings"
echo ""
