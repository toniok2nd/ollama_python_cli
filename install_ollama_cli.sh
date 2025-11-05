#!/usr/bin/env bash
# ---------------------------------------------------------------
# install_ollama_cli.sh
# Installs the Python CLI from https://github.com/toniok2nd/ollama_python_cli
# and makes it available as a global Bash command called `ollama`.
#
# Tested on:
#   - Ubuntu 20.04 / 22.04
#
# Requirements:
#   - git
#   - python3 (>=3.8)
#   - pip3
# ---------------------------------------------------------------

set -euo pipefail

# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------
log()    { echo -e "\e[1;34m[+] $*\e[0m"; }   # blue bold
error()  { echo -e "\e[1;31m[-] $*\e[0m" >&2; exit 1; }
warn()   { echo -e "\e[1;33m[!] $*\e[0m"; }

# -------------------------------------------------------------------------
# Detect the operating system / package manager
# -------------------------------------------------------------------------
detect_pkg_manager() {
    case "$(uname -s)" in
        Linux*)
            if command -v apt-get   &>/dev/null; then echo "apt";   return; fi
            if command -v dnf       &>/dev/null; then echo "dnf";   return; fi
            if command -v yum       &>/dev/null; then echo "yum";   return; fi
            if command -v pacman    &>/dev/null; then echo "pacman";return; fi
            error "Unsupported Linux package manager"; exit 1
            ;;
        Darwin*)
            if command -v brew &>/dev/null; then echo "brew"; return; fi
            error "Homebrew not found on macOS – please install it first"
            exit 1
            ;;
        CYGWIN*|MINGW*|MSYS*)
            if command -v choco &>/dev/null; then echo "choco"; return; fi
            error "Chocolatey not found on Windows – please install it first"
            exit 1
            ;;
        *)
            error "Unsupported OS: $(uname -s)"; exit 1
            ;;
    esac
}

# -------------------------------------------------------------------------
# Install fzf if it is missing
# -------------------------------------------------------------------------
install_fzf() {
    if command -v fzf &>/dev/null; then
        log "✅ fzf already installed"
        return
    fi

    local mgr
    mgr=$(detect_pkg_manager)

    log "🔧 Installing fzf via $mgr …"

    case "$mgr" in
        apt)
            sudo apt-get update -qq
            sudo apt-get install -y -qq fzf
            ;;
        dnf|yum)
            sudo "$mgr" install -y -qq fzf
            ;;
        pacman)
            sudo pacman -Sy --noconfirm fzf
            ;;
        brew)
            brew install fzf
            # Homebrew’s formula does not automatically configure shell integration,
            # but the CLI only needs the binary, so we’re done.
            ;;
        choco)
            # On Windows we install the “fzf” package from the community repo.
            choco install -y fzf
            ;;
        *)
            error "Package manager $mgr not supported for fzf installation"
            exit 1
            ;;
    esac

    if command -v fzf &>/dev/null; then
        log "✅ fzf installed successfully"
    else
        error "❌ fzf installation failed – please install it manually"
        exit 1
    fi
}

# -------------------------------------------------------------------------
# Verify required commands are present (including fzf)
# -------------------------------------------------------------------------
check_requirements() {
    local missing=()
    local REQUIRED_CMDS=(
        curl   # used to fetch binaries
        tar    # used to extract archives
        gzip   # required for .tar.gz extraction
        fzf    # interactive fuzzy finder (now a hard requirement)
    )

    for cmd in "${REQUIRED_CMDS[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if (( ${#missing[@]} )); then
        error "Missing required command(s): ${missing[*]}"
        warn "Attempting to install missing components…"
        # We try to install only the missing ones that we know how to handle.
        for pkg in "${missing[@]}"; do
            [[ "$pkg" == "fzf" ]] && continue   # fzf already handled by install_fzf()
        done
        # If there are still missing commands after the auto‑install, abort.
        error "Please install the missing tools and re‑run the script."
        exit 1
    fi
}

# ---------------------------------------------------------------
# 1. Verify prerequisites
# ---------------------------------------------------------------

log "🚀 Starting preriquisites installation"

# 1️⃣ Ensure fzf is present before anything else that might rely on it
install_fzf

# 2️⃣ Check other requirements (curl, tar, gzip, …)
check_requirements

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
