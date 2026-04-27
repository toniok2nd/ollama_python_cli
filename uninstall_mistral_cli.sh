#!/usr/bin/env bash
# ---------------------------------------------------------------
# uninstall_mistral_cli.sh
# Uninstalls the Mistral Python CLI and removes all related files.
#
# This script removes:
#   - The command wrapper (mymistral)
#   - The repository clone (~/.local/mistral_python_cli)
#   - Bash autocompletion entries
#   - PATH modifications in .bashrc
# ---------------------------------------------------------------

set -euo pipefail

# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------
log()    { echo -e "\e[1;34m[+] $*\e[0m"; }   # blue bold
error()  { echo -e "\e[1;31m[-] $*\e[0m" >&2; exit 1; }
warn()   { echo -e "\e[1;33m[!] $*\e[0m"; }
info()   { echo -e "\e[1;32m[✓] $*\e[0m"; }   # green bold

# ---------------------------------------------------------------
# 1. Confirm uninstallation
# ---------------------------------------------------------------
echo ""
warn "This will uninstall the Mistral Python CLI."
echo ""
echo "The following will be removed:"
echo "  - Command wrapper: mymistral"
echo "  - Repository: ~/.local/mistral_python_cli"
echo "  - Virtual environment"
echo "  - Bash autocompletion entries"
echo ""

if [[ -t 0 ]]; then
    read -p "Are you sure you want to continue? [y/N] " confirm
    if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
        log "Uninstallation cancelled."
        exit 0
    fi
else
    # Non-interactive mode - require --force flag
    if [[ "${1:-}" != "--force" ]]; then
        error "Non-interactive mode: use --force to confirm uninstallation"
    fi
fi

# ---------------------------------------------------------------
# 2. Define paths
# ---------------------------------------------------------------
REPO_BASE="${HOME}/.local/mistral_python_cli"

# Detect wrapper directory
if [ -f /usr/local/bin/mymistral ]; then
    WRAPPER_DIR="/usr/local/bin"
elif [ -f "${HOME}/.local/bin/mymistral" ]; then
    WRAPPER_DIR="${HOME}/.local/bin"
else
    WRAPPER_DIR=""
fi

WRAPPER_PATH="${WRAPPER_DIR:+${WRAPPER_DIR}/}mymistral"
COMPLETION_FILE="${REPO_BASE}/mymistral_completion.bash"

# ---------------------------------------------------------------
# 3. Remove the command wrapper
# ---------------------------------------------------------------
if [ -n "$WRAPPER_DIR" ] && [ -f "$WRAPPER_PATH" ]; then
    log "Removing command wrapper from $WRAPPER_PATH..."
    sudo rm -f "$WRAPPER_PATH" 2>/dev/null || rm -f "$WRAPPER_PATH"
    info "Command wrapper removed"
else
    warn "Command wrapper not found (already removed?)"
fi

# ---------------------------------------------------------------
# 4. Remove the repository and virtual environment
# ---------------------------------------------------------------
if [ -d "$REPO_BASE" ]; then
    log "Removing repository from $REPO_BASE..."
    rm -rf "$REPO_BASE"
    info "Repository removed"
else
    warn "Repository not found (already removed?)"
fi

# ---------------------------------------------------------------
# 5. Clean up .bashrc entries
# ---------------------------------------------------------------
if [ -f "${HOME}/.bashrc" ]; then
    log "Cleaning up .bashrc..."
    
    # Create a backup
    cp "${HOME}/.bashrc" "${HOME}/.bashrc.mistral_backup"
    
    # Remove PATH export line
    if grep -q "mistral_python_cli" "${HOME}/.bashrc" 2>/dev/null; then
        # Remove the comment line
        sed -i '/# Added by mistral_python_cli installer/d' "${HOME}/.bashrc"
        # Remove the PATH export line
        sed -i '/mistral_python_cli/d' "${HOME}/.bashrc"
        # Remove the completion sourcing line
        sed -i '/mymistral_completion.bash/d' "${HOME}/.bashrc"
        info "Cleaned up .bashrc entries"
    else
        warn "No mistral_python_cli entries found in .bashrc"
    fi
fi

# ---------------------------------------------------------------
# 6. Clean up .zshrc entries (if applicable)
# ---------------------------------------------------------------
if [ -f "${HOME}/.zshrc" ]; then
    log "Cleaning up .zshrc..."
    
    if grep -q "mistral_python_cli" "${HOME}/.zshrc" 2>/dev/null; then
        sed -i '/# Added by mistral_python_cli installer/d' "${HOME}/.zshrc"
        sed -i '/mistral_python_cli/d' "${HOME}/.zshrc"
        sed -i '/mymistral_completion.bash/d' "${HOME}/.zshrc"
        info "Cleaned up .zshrc entries"
    fi
fi

# ---------------------------------------------------------------
# 7. Summary
# ---------------------------------------------------------------
echo ""
log "🗑️  Uninstallation complete!"
echo ""
echo "The following were removed:"
echo "  - Command wrapper: ${WRAPPER_PATH:-N/A}"
echo "  - Repository: $REPO_BASE"
echo "  - Virtual environment"
echo "  - Bash autocompletion entries"
echo ""
echo "A backup of your .bashrc was saved to: ${HOME}/.bashrc.mistral_backup"
echo ""
echo "To complete the uninstallation:"
echo "  1. Run: source ~/.bashrc  (or open a new terminal)"
echo "  2. Verify: command -v mymistral  (should return nothing)"
echo ""
