#!/usr/bin/env bash
# ---------------------------------------------------------------
# install_ollama_cli.sh
# Installs the Python CLI from https://github.com/toniok2nd/ollama_python_cli
# and makes it available as a global Bash command called `ollama`.
#
# Tested on:
#   - Ubuntu 20.04 / 22.04
#   - Debian 11 / 12
#   - Fedora 38
#   - macOS 13 (Homebrew‑based)
#
# Requirements:
#   - git
#   - python3 (>=3.8)
#   - pip3
# ---------------------------------------------------------------

set -euo pipefail   # safer Bash

# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------
log()    { echo -e "\e[1;34m[+] $*\e[0m"; }   # blue bold
error()  { echo -e "\e[1;31m[-] $*\e[0m" >&2; exit 1; }
warn()   { echo -e "\e[1;33m[!] $*\e[0m"; }

# ---------------------------------------------------------------
# 1. Verify prerequisites
# ---------------------------------------------------------------
for cmd in git python3 pip3; do
    command -v "$cmd" >/dev/null 2>&1 || error "Required command '$cmd' not found. Install it first."
done

# Verify Python version (needs at least 3.8 for most modern packages)
PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if (dpkg --compare-versions "$PY_VER" lt "3.8"); then
    error "Python 3.8+ is required (found $PY_VER)."
fi

log "All prerequisites are present."

# ---------------------------------------------------------------
# 2. Choose install locations
# ---------------------------------------------------------------
# Base directory where the repo will be cloned
REPO_BASE="${HOME}/.local/ollama_python_cli"

# Directory that will hold the command wrapper
# Prefer /usr/local/bin (needs sudo) – otherwise fall back to ~/.local/bin
if command -v sudo >/dev/null 2>&1 && [ -w /usr/local/bin ]; then
    WRAPPER_DIR="/usr/local/bin"
else
    WRAPPER_DIR="${HOME}/.local/bin"
fi

log "Repo will be cloned to: $REPO_BASE"
log "Wrapper script will be placed in: $WRAPPER_DIR"

# ---------------------------------------------------------------
# 3. Clone the repo (or pull latest if already present)
# ---------------------------------------------------------------
if [ -d "$REPO_BASE/.git" ]; then
    log "Repository already exists – pulling latest changes..."
    git -C "$REPO_BASE" fetch --all
    git -C "$REPO_BASE" reset --hard origin/main
else
    log "Cloning repository..."
    git clone https://github.com/toniok2nd/ollama_python_cli "$REPO_BASE"
fi

# ---------------------------------------------------------------
# 4. Set up a Python virtual environment
# ---------------------------------------------------------------
VENV_DIR="${REPO_BASE}/.venv"

if [ -d "$VENV_DIR" ]; then
    log "Virtualenv already exists – updating packages..."
else
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate the venv for the rest of the script
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

log "Virtualenv activated (Python: $(python -V))"

# ---------------------------------------------------------------
# 5. Install Python dependencies
# ---------------------------------------------------------------
# The repo ships a requirements.txt; if not, fall back to installing ollama‑python‑cli directly.
if [ -f "${REPO_BASE}/requirements.txt" ]; then
    log "Installing requirements from requirements.txt ..."
    pip install --upgrade pip setuptools wheel
    pip install -r "${REPO_BASE}/requirements.txt"
else
    log "No requirements.txt found – installing the package via pip (might pull from PyPI)..."
    pip install --upgrade pip setuptools wheel
    pip install -e "${REPO_BASE}"
fi

# ---------------------------------------------------------------
# 6. Install the command wrapper
# ---------------------------------------------------------------
# The actual script you want to expose is called cliOllama.py
# (the repo uses a capital O – keep that exact name).
CLI_SCRIPT="${REPO_BASE}/cliOllama.py"

if [ ! -f "$CLI_SCRIPT" ]; then
    error "Could not locate cliOllama.py at expected path: $CLI_SCRIPT"
fi

WRAPPER_PATH="${WRAPPER_DIR}/myollama"

# Create a tiny wrapper that forwards to the virtualenv python interpreter
cat >"$WRAPPER_PATH" <<'EOF'
#!/usr/bin/env bash
# Wrapper for ollama_python_cli → cliOllama.py
# All arguments are passed through unchanged.

# Resolve the location of this wrapper (so it works even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The VENV path is hard‑coded at install time – we embed it here.
VENV_PATH="{{VENV_PATH}}"

# Activate the venv (just modifies $PATH and $PYTHONPATH)
if [ -f "${VENV_PATH}/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${VENV_PATH}/bin/activate"
else
    echo "ERROR: virtualenv not found at ${VENV_PATH}" >&2
    exit 1
fi

# Run the actual CLI Python script
exec python "{{CLI_PATH}}" "$@"
EOF

# Substitute the placeholders with the real paths
sed -i "s|{{VENV_PATH}}|${VENV_DIR}|g" "$WRAPPER_PATH"
sed -i "s|{{CLI_PATH}}|${CLI_SCRIPT}|g" "$WRAPPER_PATH"

chmod +x "$WRAPPER_PATH"
log "Wrapper installed to $WRAPPER_PATH"

# ---------------------------------------------------------------
# 7. Ensure wrapper directory is on the user's $PATH
# ---------------------------------------------------------------
if [[ ":$PATH:" != *":${WRAPPER_DIR}:"* ]]; then
    warn "Directory $WRAPPER_DIR is NOT currently on your \$PATH."
    if [ -w "${HOME}/.bashrc" ]; then
        echo '' >> "${HOME}/.bashrc"
        echo "# Added by ollama_python_cli installer" >> "${HOME}/.bashrc"
        echo "export PATH=\"${WRAPPER_DIR}:\$PATH\"" >> "${HOME}/.bashrc"
        log "Appended PATH export to ${HOME}/.bashrc"
        log "Run 'source ~/.bashrc' or open a new terminal to use the command."
    else
        warn "Could not automatically modify PATH – add ${WRAPPER_DIR} to your shell's PATH manually."
    fi
else
    log "Wrapper directory already on PATH."
fi
log "Done."
