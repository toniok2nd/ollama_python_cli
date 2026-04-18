#!/usr/bin/env bash
# ---------------------------------------------------------------
# uninstall_ollama_cli.sh
# Uninstalls the Python CLI from your system.
# ---------------------------------------------------------------

set -euo pipefail

log()    { echo -e "\e[1;34m[+] $*\e[0m"; }   # blue bold
warn()   { echo -e "\e[1;33m[!] $*\e[0m"; }

REPO_BASE="${HOME}/.local/ollama_python_cli"

# Detect wrapper directory
if [ -f "/usr/local/bin/myollama" ]; then
    WRAPPER_PATH="/usr/local/bin/myollama"
elif [ -f "${HOME}/.local/bin/myollama" ]; then
    WRAPPER_PATH="${HOME}/.local/bin/myollama"
else
    WRAPPER_PATH=""
fi

# 1. Remove the wrapper
if [ -n "$WRAPPER_PATH" ]; then
    log "Removing wrapper at $WRAPPER_PATH ..."
    if [ -w "$(dirname "$WRAPPER_PATH")" ]; then
        rm -f "$WRAPPER_PATH"
    else
        sudo rm -f "$WRAPPER_PATH"
    fi
else
    warn "Wrapper 'myollama' not found in standard locations."
fi

# 2. Remove the repository and VENV
if [ -d "$REPO_BASE" ]; then
    log "Removing repository and virtualenv at $REPO_BASE ..."
    rm -rf "$REPO_BASE"
else
    warn "Repository directory $REPO_BASE not found."
fi

# 3. Clean up .bashrc (optional, but good practice)
if [ -f "${HOME}/.bashrc" ]; then
    if grep -q "ollama_python_cli installer" "${HOME}/.bashrc"; then
        log "Cleaning up .bashrc ..."
        # Remove the marked block from .bashrc
        # This is a bit naive but matches the installer's pattern
        sed -i '/# Added by ollama_python_cli installer/,/export PATH/d' "${HOME}/.bashrc"
        # Also remove trailing empty lines if any
        sed -i '${/^[[:space:]]*$/d}' "${HOME}/.bashrc"
    fi
fi

log "Successfully uninstalled Ollama Python CLI."
log "Note: Any manual changes to your PATH or other shells might still persist."
