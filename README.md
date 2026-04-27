# Ollama & Mistral Python CLI

A powerful, feature-rich Python CLI wrapper for both **Ollama** (local models) and **Mistral AI** (cloud API) with Model Context Protocol (MCP) integration.

---

## 🤖 Choose Your Model Provider

### Local Models (Ollama)
Run open-source models locally on your machine. Free, private, no API keys needed.

```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash
```

### Cloud Models (Mistral AI)
Access powerful Mistral models via API. Requires API key but no local GPU needed.

```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_mistral_cli.sh | bash
```

---

## ✨ Key Features

### Common Features (Both CLI)
- **Interactive Model Selection**: Uses `fzf` to choose from available models.
- **Multi-line Input**: Supports multi-line prompts with customizable EOF marker (default `EOF`).
- **MCP Integration**: Full Model Context Protocol support for tools and extensions.
- **Rich Markdown Rendering**: Beautifully formatted responses using `rich`.
- **Element Extraction**: Commands to copy code blocks (`>>`) or tables (`||`) from responses.
- **Custom Themes**: Interactively change prompt colors and styles.
- **Shell Execution**: Run bash commands directly using `!` (e.g., `!ls`).
- **Input History**: Navigate previous inputs with arrow keys.
- **Session Management**: Save and load chat histories.
- **Voice Trigger**: Use `<<` to toggle voice recording (requires STT server).

### MCP Servers (Available for Both)
- **File System**: Let AI read/write files in your workspace.
- **Image Generation**: Create images via Pollinations AI (no API key).
- **Voice TTS**: Text-to-speech with Microsoft Edge TTS.
- **Coqui TTS**: High-quality offline voice synthesis.
- **Webcam**: Capture snapshots for vision tasks.
- **Speech-to-Text**: Voice recording and transcription.
- **YouTube**: Search videos and fetch transcripts.
- **Video Editing**: Create OpenShot projects with FFmpeg.
- **Spotify**: Control playback and search music.
- **Konyks/Tuya**: Smart home device control.

---

## 🚀 Installation

### Ollama CLI (Local Models)

#### Installation Tiers

**1. Light (Core Only)**
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash -s -- --light
```

**2. Medium (Recommended)**
Adds Image Generation and Voice Synthesis.
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash -s -- --medium
```

**3. Full (Multimedia, Smart Home & Music)**
Adds Webcam, Voice Recording, YouTube, Video Editing, Konyks, and Spotify.
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash -s -- --full
```

### Mistral CLI (Cloud Models)

**Standard Installation**
```bash
curl -sSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_mistral_cli.sh | bash
```

**Configure API Key**
After installation, set your Mistral API key:
```bash
mymistral --config-mistral
```
Or set environment variable:
```bash
export MISTRAL_API_KEY="your-api-key-here"
```

Get your API key from: https://console.mistral.ai/api-keys/

### Manual Install

**Ollama:**
```bash
git clone https://github.com/toniok2nd/ollama_python_cli
cd ollama_python_cli
python3 -m venv VENV
source VENV/bin/activate
pip install -r requirements.txt
```

**Mistral:**
```bash
git clone https://github.com/toniok2nd/ollama_python_cli
cd ollama_python_cli
python3 -m venv VENV
source VENV/bin/activate
pip install -r requirements_mistral.txt
```

---

## 🛠 Usage

### Ollama CLI

Ensure Ollama is running (`ollama serve`).

**Basic Usage:**
```bash
myollama
myollama --model mistral:latest
```

**With MCP Servers:**
```bash
myollama --enable-fs              # File system access
myollama --enable-image           # Image generation
myollama --enable-voice           # Text-to-speech
myollama --enable-webcam          # Webcam capture
myollama --enable-tss             # Speech-to-text
myollama --enable-youtube         # YouTube search
myollama --enable-video           # Video editing
myollama --enable-konyks          # Smart home
myollama --enable-spotify         # Music control
```

### Mistral CLI

**Basic Usage:**
```bash
mymistral
mymistral -m mistral-small-latest
mymistral -m mistral-large-latest
```

**With MCP Servers:**
```bash
mymistral --enable-fs
mymistral --enable-image
mymistral --enable-voice
# ... (same MCP flags as Ollama CLI)
```

---

## 🔒 Authentication & Configuration

### Mistral AI
1. Get API key from https://console.mistral.ai/api-keys/
2. Configure via:
   - `mymistral --config-mistral`
   - `/config-mistral` inside the chat
   - `MISTRAL_API_KEY` environment variable

### Spotify
1. Create app on [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Set Redirect URI: `http://127.0.0.1:8888/callback`
3. Configure via `/config-spotify` inside the CLI

### Konyks / Tuya Smart Home
1. Create project on [Tuya IoT Platform](https://iot.tuya.com/)
2. Enable Core Control and Authorization Token Management APIs
3. Configure via `/config-konyks` with:
   - `TUYA_CLIENT_ID`: Access ID
   - `TUYA_CLIENT_SECRET`: Access Secret
   - `TUYA_UID`: User ID
   - `TUYA_BASE_URL`: (Optional) Defaults to EU region

> [!TIP]
> Run `/settings` in the app to see the path to your `settings.json` file.

---

## ⌨️ Command Reference

| Command | Description |
| --- | --- |
| `exit` | Quit the CLI |
| `/?` | Show help menu |
| `/save` | Save current chat session |
| `/load` | Load saved chat session |
| `/settings` | Show settings.json content and path |
| `/style` | Customize prompt colors |
| `/eof` | Change EOF marker string |
| `/auto` | Toggle auto-save after responses |
| `!<cmd>` | Execute shell command |
| `>>` | List code blocks from last response |
| `>>[n]` | Show and copy code block n |
| `||` | List tables from last response |
| `||[n]` | Show and copy table n |
| `<<` | Toggle voice recording |
| `/config-spotify` | Setup Spotify credentials |
| `/config-konyks` | Setup Konyks/Tuya credentials |
| `/config-mistral` | Setup Mistral API key (Mistral CLI only) |

---

## 🗑 Uninstallation

### Ollama CLI
```bash
curl -fsSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/uninstall_ollama_cli.sh | bash
```

### Mistral CLI
```bash
curl -fsSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/uninstall_mistral_cli.sh | bash
```

---

## 📁 Project Structure

- `cliOllama.py`: Main entry point for Ollama CLI
- `cliMistral.py`: Main entry point for Mistral CLI
- `chatManager.py`: Chat history save/load management
- `markedownExtractor.py`: Code block and table extraction
- `simple_fs_server.py`: MCP file system server
- `install_ollama_cli.sh` / `uninstall_ollama_cli.sh`: Ollama install scripts
- `install_mistral_cli.sh` / `uninstall_mistral_cli.sh`: Mistral install scripts
- `requirements.txt`: Ollama CLI dependencies
- `requirements_mistral.txt`: Mistral CLI dependencies

---

## 📋 Available Mistral Models

- `mistral-large-latest` - Most powerful model
- `mistral-small-latest` - Fast and efficient
- `codestral-latest` - Code generation specialist
- `pixtral-large-latest` - Multimodal (vision + text)
- `ministral-8b-latest` - Lightweight model
- `ministral-3b-latest` - Ultra-lightweight
- `open-mistral-7b` - Open weights 7B
- `open-mixtral-8x7b` - Open weights MoE
- `open-mixtral-8x22b` - Open weights large MoE

---

## 🐛 Troubleshooting

### Ollama CLI
- Ensure Ollama is running: `ollama serve`
- List models: `ollama list`
- Pull a model: `ollama pull mistral`

### Mistral CLI
- Check API key: `echo $MISTRAL_API_KEY`
- Test connection: Run `mymistral --config-mistral`
- Verify package: `pip show mistralai`

### Common Issues
- **fzf not found**: Install with your package manager (`apt install fzf`, `brew install fzf`)
- **Command not found**: Run `source ~/.bashrc` or restart terminal
- **MCP errors**: Ensure server scripts exist in the installation directory
