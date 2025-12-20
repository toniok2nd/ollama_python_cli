# Ollama Python CLI (via official ollama library)

A powerful, feature-rich Python CLI wrapper for the official `ollama` library. This tool enhances your local Ollama experience with interactive model selection, multi-line input, custom themes, image generation, and Model Context Protocol (MCP) integration.

## ✨ Key Features

- **Image Generation**: Generate pictures directly from your chat using Pollinations AI (via MCP).
- **Webcam & Multimedia**: Capture snapshots from your webcam or record voice messages for transcription (via MCP). Supports hands-free recording with the `<<` toggle.
- **Voice Support**: Realistic text-to-speech capabilities using Microsoft Edge TTS (via MCP).
- 🤖 **Multi-Server MCP**: Concurrent support for File System, Image Generation, Voice (TTS/STT), Webcam, YouTube, and Video Editing.
- **Interactive Model Selection**: Uses `fzf` to let you choose from your locally available models.
- **Multi-line Input**: Supports multi-line prompts with a customizable EOF marker (default is `EOF`).
- **MCP Integration**: Full support for Model Context Protocol. Includes a built-in File System server to let the LLM read and write files in your workspace.
- **Rich Markdown Rendering**: Beautifully formatted responses using the `rich` library.
- **Element Extraction**: Special commands to list and copy code blocks (`>>`) or tables (`||`) from the last response.
- **Video Editing**: `--enable-video` (Full tier). Create OpenShot projects and render montages with FFmpeg (via MCP).
- **YouTube**: `--enable-youtube` (Full tier). Search videos and fetch transcripts for AI analysis.
- **Voice Trigger**: Use `<<` to toggle voice recording for hands-free prompting (requires STT).
- **Custom Themes**: Interactively change prompt colors and styles.
- **Shell Execution**: Run bash commands directly from the chat interface using `!` (e.g., `!ls`).
- **Input History**: Navigate through your previous command inputs using the vertical arrow keys (Up/Down).
- **Session Management**: Save and load chat histories. Uses a hidden `.historyList.json` file to index your sessions without cluttering your workspace.

## 🚀 Installation

## 🛠️ Installation Tiers

Choose the tier that fits your needs:

### 1. Light (Core Only)
Terminal UI, History, Shell commands, and basic MCP.
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash -s -- --light
```

### 2. Medium (Recommended)
Adds **Image Generation** and **Voice Synthesis**.
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash -s -- --medium
```

### 3. Full (Multimedia)
Adds **Webcam Capture** and **Local Voice Recording (STT)**.
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash -s -- --full
```

> [!NOTE]
> If you run the script without flags, it will prompt you to select a tier interactively.

### Manual Install
```bash
# Clone the repository
git clone https://github.com/toniok2nd/ollama_python_cli
cd ollama_python_cli

# Create a virtual environment
python3 -m venv VENV
source VENV/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 🛠 Usage

Ensure Ollama is running (`ollama serve`).

### Basic Usage
Start with interactive model selection:
```bash
myollama
```

Start with a specific model:
```bash
myollama --model mistral:latest
```

### File System Access (MCP)
Enable the Model Context Protocol file system tools to allow the AI to interact with your files.
Default to current directory:
```bash
myollama --enable-fs
```
Specify a working directory:
```bash
myollama --enable-fs /path/to/project
```

### Image Generation (MCP)
Enable the image generation tools to allow the AI to create pictures. No API key is required.
```bash
myollama --enable-image
```

### Voice Support (MCP)
Enable the voice tools to allow the AI to speak its responses.
```bash
myollama --enable-voice
```

### Webcam & Recording (MCP)
Enable vision and intent tools.
```bash
myollama --enable-webcam --enable-tss
```


### Load a Previous Chat
```bash
myollama --load previous_session.json
```

## ⌨️ Command Reference

| Command | Description |
| --- | --- |
| `exit` | Quit the CLI. |
| `/?` | Show the help menu with internal options. |
| `/save` | Save the current chat session to a JSON file. |
| `/load` | Interactively select and load a saved chat session from history. |
| `/settings` | Show the `settings.json` file content and path. |
| `/style` | Interactively customize prompt colors (`style_b` and `style_g`). |
| `/eof` | Change the multi-line input termination string (default `EOF`). |
| `/auto` | Toggle automatic saving after each response (requires initial `/save`). |
| `! <cmd>`| Execute a shell command and see the output (e.g., `!ls`). |
| `>>` | List all code blocks from the last AI response. |
| `>>[n]` | Show code block `n` and copy it to the clipboard (e.g., `>>0`). |
| `||` | List all tables from the last AI response. |
| `||[n]` | Show table `n` and copy it to the clipboard (e.g., `||0`). |
| `<<` | Toggle voice recording (requires `--enable-tss`). |

## 📁 Project Structure

- `cliOllama.py`: The main entry point and terminal UI logic.
- `chatManager.py`: Handles saving, loading, and indexing chat histories.
- `markedownExtractor.py`: Low-level parsing for code blocks and tables in responses.
- `simple_fs_server.py`: The MCP server implementation for file system operations.
- `install_ollama_cli.sh` / `uninstall_ollama_cli.sh`: Installation scripts.

## 🗑 Uninstallation
```bash
curl -fsSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/uninstall_ollama_cli.sh | bash
```
