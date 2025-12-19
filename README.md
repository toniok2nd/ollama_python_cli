# Ollama Python CLI (via official ollama library)

A Python CLI wrapper that uses the official `ollama` Python library to interact with your local Ollama instance.

## Requirements

- Python 3.8+
- `ollama` (running locally)
- `fzf` (for interactive model selection)

## Installation

### Automated Install
```bash
curl -fsSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash
```
This will install a global `myollama` command on your system.

### Uninstallation
```bash
curl -fsSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/uninstall_ollama_cli.sh | bash
```
This will remove the virtual environment, the repository, and the global command.

### Manual Install
```bash
# Clone repository
git clone https://github.com/toniok2nd/ollama_python_cli
cd ollama_python_cli

# Create virtual environment
python3 -m venv VENV
source VENV/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

Ensure Ollama is running (`ollama serve`).

### Run with a specific model
```bash
myollama --model mistral:latest
```

### Enable File System Access (MCP)
To enable file operations (defaults to current directory):
```bash
myollama --enable-fs
```
Or specify a working directory:
```bash
myollama --enable-fs /path/to/project
```

### Interactive Selection
If you run without arguments, it use `ollama list` and `fzf` to let you select an available model:
```bash
myollama
```
