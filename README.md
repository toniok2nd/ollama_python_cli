# Ollama Python CLI (via official ollama library)

A powerful, feature-rich Python CLI wrapper for the official `ollama` library. This tool enhances your local Ollama experience with interactive model selection, multi-line input, custom themes, image generation, and Model Context Protocol (MCP) integration.

## ✨ Key Features

- **Image Generation**: Generate pictures directly from your chat using Pollinations AI (via MCP).
- **Webcam & Multimedia**: Capture snapshots from your webcam or record voice messages for transcription (via MCP). Supports hands-free recording with the `<<` toggle.
- **Voice Support**: Realistic text-to-speech capabilities using Microsoft Edge TTS (via MCP).
- 🤖 **Multi-Server MCP**: Concurrent support for File System, Image Generation, Voice (TTS/STT), Webcam, YouTube, Video Editing, Smart Home (Konyks), and Spotify.
- **Spotify**: Search music and control playback (play/pause/next/previous/volume) directly from the chat. **Auto-activates when configured.**
- **Konyks / Tuya**: Control your smart home devices (lights, plugs, etc.) directly from the chat. **Auto-activates when configured.**
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

### 3. Full (Multimedia, Smart Home & Music)
Adds **Webcam Capture**, **Local Voice Recording (STT)**, **Konyks/Tuya Smart Home**, and **Spotify** support.
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

### Konyks / Tuya Smart Home (MCP)
Control your smart devices. Requires Tuya Cloud credentials in `settings.json`.
> [!NOTE]
> Once configured via `/config-konyks`, this server starts automatically. You only need the flag for manual overrides.
```bash
myollama --enable-konyks
```

### 🔒 Authentication & Configuration

Some MCP servers (Full tier) require credentials. You can set them via:
1.  **CLI Flags** (Best for first-time setup and shell autocompletion):
    ```bash
    myollama --config-spotify
    myollama --config-konyks
    ```
2.  **Slash Commands** (Inside the chat): `/config-spotify` or `/config-konyks`.
3.  **Manual Edit**: Add keys directly to `settings.json` or as **Environment Variables**.

> [!TIP]
> Run `/settings` in the app to see the path to your `settings.json` file.

#### 🎵 Spotify
1. Create an app on the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Set the Redirect URI to `http://127.0.0.1:8888/callback`.
3. **Assisted Configuration**:
   - Run `/config-spotify` inside `myollama`.
   - The CLI will guide you through the login process and securely save your access token.
   - **No manual flag required**: Once authenticated, Spotify tools are available every time you start `myollama`.

> [!TIP]
> **Why `127.0.0.1` instead of `localhost`?**
> Spotify and many modern browsers have deprecated the string `localhost` for OAuth redirect URIs due to security policies. Using the explicit loopback IP `127.0.0.1` allows you to continue using unencrypted HTTP for local development.

#### 🏠 Konyks / Tuya Smart Home
1. Create a project on the [Tuya IoT Platform](https://iot.tuya.com/).
2. Enable the **Core Control** and **Authorization Token Management** APIs.
3. Link your Konyks/Tuya app account to the project.
4. **Configuration**:
   - `TUYA_CLIENT_ID`: Your Access ID/Client ID.
   - `TUYA_CLIENT_SECRET`: Your Access Secret/Client Secret.
   - `TUYA_UID`: Your User ID (found in the Cloud -> Link Tuya App Account tab).
   - `TUYA_BASE_URL`: (Optional) Defaults to `https://openapi.tuyaeu.com` (Europe).

#### 📺 YouTube
- **No authentication required** for core search and transcript features.

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
| `!<cmd>`| Execute a shell command and see the output (e.g., `!ls`). |
| `>>` | List all code blocks from the last AI response. |
| `>>[n]` | Show code block `n` and copy it to the clipboard (e.g., `>>0`). |
| `||` | List all tables from the last AI response. |
| `||[n]` | Show table `n` and copy it to the clipboard (e.g., `||0`). |
| `<<` | Toggle voice recording (requires `--enable-tss`). |
| `/config-spotify` | Interactively setup Spotify credentials in `settings.json`. |
| `/config-konyks` | Interactively setup Konyks (Tuya) credentials in `settings.json`. |

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
