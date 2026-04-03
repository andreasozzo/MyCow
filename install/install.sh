#!/usr/bin/env bash
# MyCow Installer per Mac/Linux
# Uso: curl -fsSL https://mycow.dev/install.sh | bash

set -euo pipefail

MYCOW_REPO_URL="https://github.com/andreasozzo/MyCow/archive/refs/heads/main.zip"
INSTALL_DIR="$HOME/MyCow"
VENV_DIR="$INSTALL_DIR/venv"
MIN_PYTHON_MINOR=11  # 3.11+

# --- Helpers ------------------------------------------------------------

step()  { echo ""; echo ">> $1"; }
ok()    { echo "   OK  $1"; }
warn()  { echo "   !   $1"; }
fail()  { echo ""; echo "[ERRORE] $1" >&2; exit 1; }

# Colori (solo se terminale interattivo)
if [ -t 1 ]; then
    step()  { echo ""; echo -e "\033[36m>> $1\033[0m"; }
    ok()    { echo -e "   \033[32mOK\033[0m  $1"; }
    warn()  { echo -e "   \033[33m!\033[0m   $1"; }
    fail()  { echo -e "\n\033[31m[ERRORE] $1\033[0m" >&2; exit 1; }
fi

# --- 1. Verifica Python -------------------------------------------------

step "Verifica Python 3.11+"

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge $MIN_PYTHON_MINOR ]; then
            PYTHON_CMD="$cmd"
            ok "Trovato: $cmd $ver"
            break
        fi
    fi
done

[ -z "$PYTHON_CMD" ] && fail "Python 3.11+ non trovato. Scarica da https://python.org/downloads/"

# --- 2. Verifica Claude Code CLI ----------------------------------------

step "Verifica Claude Code CLI"

if command -v claude &>/dev/null; then
    ok "Trovato: $(claude --version 2>&1 | head -1)"
else
    warn "Claude Code CLI non trovato nel PATH."
    warn "Installa con: npm install -g @anthropic-ai/claude-code"
    warn "MyCow verra' installato ma non funzionera' senza Claude Code."
fi

# --- 3. Download MyCow --------------------------------------------------

step "Download MyCow"

if [ -d "$INSTALL_DIR" ]; then
    warn "Cartella $INSTALL_DIR gia' esistente. Aggiorno solo le dipendenze."
else
    TMP_ZIP=$(mktemp /tmp/mycow_XXXXXX.zip)
    TMP_EXTRACT=$(mktemp -d /tmp/mycow_extract_XXXXXX)

    echo "   Scarico da $MYCOW_REPO_URL ..."
    if command -v curl &>/dev/null; then
        curl -fsSL "$MYCOW_REPO_URL" -o "$TMP_ZIP"
    elif command -v wget &>/dev/null; then
        wget -q "$MYCOW_REPO_URL" -O "$TMP_ZIP"
    else
        fail "curl o wget necessari per il download."
    fi

    unzip -q "$TMP_ZIP" -d "$TMP_EXTRACT"

    # La zip di GitHub estrae in una sottocartella (es. mycow-main)
    INNER_DIR=$(find "$TMP_EXTRACT" -maxdepth 1 -mindepth 1 -type d | head -1)
    mv "$INNER_DIR" "$INSTALL_DIR"

    rm -f "$TMP_ZIP"
    rm -rf "$TMP_EXTRACT"
    ok "Estratto in $INSTALL_DIR"
fi

# --- 4. Crea venv -------------------------------------------------------

step "Creazione ambiente virtuale Python"

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    ok "Venv creato in $VENV_DIR"
else
    ok "Venv gia' esistente"
fi

# --- 5. Installa dipendenze ---------------------------------------------

step "Installazione dipendenze Python"

"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
ok "Dipendenze installate"

# --- 6. Configura .env --------------------------------------------------

step "Configurazione .env"

ENV_FILE="$INSTALL_DIR/.env"
ENV_EXAMPLE="$INSTALL_DIR/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        ok ".env creato da .env.example"
    else
        cat > "$ENV_FILE" <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BRAVE_API_KEY=
MYCOW_PORT=3333
MYCOW_LOG_LEVEL=INFO
EOF
        ok ".env creato con valori di default"
    fi
else
    ok ".env gia' esistente (non sovrascritto)"
fi

# --- 7. Rimuovi skill dev -----------------------------------------------

step "Rimozione skill di sviluppo interno"

for skill in ux-premium security-first; do
    skill_path="$INSTALL_DIR/skills/global/$skill"
    if [ -d "$skill_path" ]; then
        rm -rf "$skill_path"
        ok "Rimossa: $skill"
    fi
done

# --- 8. Crea script wrapper 'mycow' ------------------------------------

step "Creazione comando 'mycow'"

WRAPPER="$INSTALL_DIR/mycow"
cat > "$WRAPPER" <<'WRAPPER_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/daemon/main.py" "$@"
WRAPPER_EOF
chmod +x "$WRAPPER"
ok "Creato: $WRAPPER"

# --- 9. Registra nel PATH -----------------------------------------------

step "Registrazione nel PATH"

LINKED=false

# Prova symlink in /usr/local/bin (richiede permessi)
if [ -w "/usr/local/bin" ] || sudo -n true 2>/dev/null; then
    if sudo ln -sf "$WRAPPER" /usr/local/bin/mycow 2>/dev/null; then
        ok "Symlink creato: /usr/local/bin/mycow"
        LINKED=true
    fi
fi

if [ "$LINKED" = false ]; then
    # Fallback: aggiunge al PATH in .bashrc e .zshrc
    EXPORT_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""
    for rc_file in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$rc_file" ] && ! grep -qF "$INSTALL_DIR" "$rc_file"; then
            echo "" >> "$rc_file"
            echo "# MyCow" >> "$rc_file"
            echo "$EXPORT_LINE" >> "$rc_file"
            ok "Aggiunto PATH in $rc_file"
        fi
    done
    warn "Riapri il terminale (o esegui: source ~/.bashrc) per usare 'mycow'"
fi

# --- Fine ---------------------------------------------------------------

echo ""
echo "=========================================="
echo "  MyCow installato con successo!"
echo "=========================================="
echo ""
echo "  Avvia il daemon:    mycow start"
echo "  Ferma il daemon:    mycow stop"
echo "  Stato:              mycow status"
echo ""
echo "  Configura i tuoi secrets in: $ENV_FILE"
echo "  Oppure aprendo la Web UI:    http://127.0.0.1:3333 → Settings"
echo ""
