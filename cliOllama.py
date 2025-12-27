from prompt_toolkit.completion import WordCompleter, Completer
from mcp import ClientSession, StdioServerParameters
from prompt_toolkit import PromptSession, prompt
from markedownExtractor import MarkdownExtractor
from mcp.client.stdio import stdio_client
from prompt_toolkit.styles import Style
from mcp.types import CallToolResult
from typing import Any, Dict, Union 
from chatManager import ChatManager
from rich.markdown import Markdown
from rich.console import Console
from rich.emoji import Emoji
from rich.text import Text
from pathlib import Path
from rich.live import Live
import ollama
import subprocess
import argparse
import pyperclip
import asyncio
import json
import sys
import re
import argcomplete


# ---------------------------------------------------------------------------
# Helper functions for loading and persisting user settings (styles, EOF marker,
# voice trigger, etc.).  Settings are stored in a JSON file next to this script.
# ---------------------------------------------------------------------------
def load_settings():
    """Load settings from ``settings.json`` merging with defaults.

    Returns
    -------
    dict
        The resulting settings dictionary.
    """
    settings_path = Path(__file__).parent / "settings.json"
    defaults = {
        "style_b": "#ffffff bg:#0e49ba",
        "style_g": "#ffffff bg:green",
        "eof_string": "EOF",
        "voice_trigger": "<<",
        "stt_duration": 10
    }
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return {**defaults, **json.load(f)}
        except Exception:
            # Corrupt file – fall back to defaults silently.
            return defaults
    return defaults

def save_settings(settings_dict):
    """Persist ``settings_dict`` back to ``settings.json``.

    Parameters
    ----------
    settings_dict : dict
        Settings to write.
    """
    settings_path = Path(__file__).parent / "settings.json"
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Initialise global style objects based on loaded settings.
# ---------------------------------------------------------------------------
settings = load_settings()
style_b = Style.from_dict({'': settings['style_b']})
style_g = Style.from_dict({'': settings['style_g']})

# ---------------------------------------------------------------------------
# Core chat handling – streams responses from Ollama, handles tool calls, and
# returns incremental tokens for live rendering.
# ---------------------------------------------------------------------------
async def run_chat_turn(model, messages, sessions=None):
    """Execute a single turn of the conversation.

    This function streams the Ollama response, detects tool calls, executes them
    via any active MCP sessions, and yields the response tokens one‑by‑one so the
    caller can update a live UI.
    """
    # -------------------------------------------------------------------
    # Gather tool specifications from every supplied MCP session.
    # -------------------------------------------------------------------
    tools = []
    tool_to_session = {}  # Map tool name → session that provides it
    if sessions:
        for session in sessions:
            try:
                result = await session.list_tools()
                for tool in result.tools:
                    tools.append({
                        'type': 'function',
                        'function': {
                            'name': tool.name,
                            'description': tool.description,
                            'parameters': tool.inputSchema
                        }
                    })
                    tool_to_session[tool.name] = session
            except Exception:
                # Silently ignore a session that cannot list its tools.
                continue

    # -------------------------------------------------------------------
    # Main loop – we may need to iterate multiple times if the model calls
    # tools that produce additional output.
    # -------------------------------------------------------------------
    while True:
        try:
            stream = ollama.chat(model=model, messages=messages, tools=tools if tools else None, stream=True)
            final_message = {'role': 'assistant', 'content': '', 'tool_calls': []}
            for chunk in stream:
                # ----------------------------------------------------------------
                # Append normal text content.
                # ----------------------------------------------------------------
                content = chunk.get('message', {}).get('content', '')
                if content:
                    final_message['content'] += content
                    yield content
                # ----------------------------------------------------------------
                # Accumulate any tool calls present in the streamed chunk.
                # ----------------------------------------------------------------
                if 'tool_calls' in chunk.get('message', {}):
                    tcs = chunk['message']['tool_calls']
                    for tc in tcs:
                        # Convert to plain dict for JSON safety.
                        if hasattr(tc, 'model_dump'):
                            final_message['tool_calls'].append(tc.model_dump())
                        elif hasattr(tc, 'dict'):
                            final_message['tool_calls'].append(tc.dict())
                        else:
                            final_message['tool_calls'].append({
                                'type': 'function',
                                'function': {
                                    'name': getattr(tc.function, 'name', None),
                                    'arguments': getattr(tc.function, 'arguments', None)
                                }
                            })
        except Exception as e:
            yield f"\n[Ollama Error: {e}]"
            return

        # -------------------------------------------------------------------
        # End of stream – post‑process the collected assistant message.
        # -------------------------------------------------------------------
        if not final_message['tool_calls']:
            del final_message['tool_calls']
        messages.append(final_message)
        if not final_message.get('tool_calls'):
            break  # No tools were called – conversation turn complete.

        # -------------------------------------------------------------------
        # Execute each tool call and feed the results back to the model.
        # -------------------------------------------------------------------
        for tool_call in final_message['tool_calls']:
            fn_name = tool_call['function']['name']
            fn_args = tool_call['function']['arguments']
            session = tool_to_session.get(fn_name)
            if not session:
                messages.append({
                    'role': 'tool',
                    'content': f"Error: Tool '{fn_name}' not found in any active session.",
                    'name': fn_name
                })
                yield f"\n[Error: Tool {fn_name} not found]"
                continue
            yield f"\n[Executing tool: {fn_name}...]"
            try:
                result = await session.call_tool(fn_name, arguments=fn_args)
                # Extract text content from the tool response (handles a few
                # possible shapes).
                tool_output = ""
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        tool_output += content_item.text
                    elif isinstance(content_item, dict) and 'text' in content_item:
                        tool_output += content_item['text']
                    elif hasattr(content_item, 'data'):
                        tool_output += "\n[Image output received]"
                messages.append({
                    'role': 'tool',
                    'content': tool_output,
                    'name': fn_name
                })
            except Exception as e:
                messages.append({
                    'role': 'tool',
                    'content': f"Error executing tool: {e}",
                    'name': fn_name
                })
                yield f" [Error: {e}]"
        # Loop back – the new tool results are now in *messages* and the model
        # will be called again to continue the turn.

# ---------------------------------------------------------------------------
# Argument validation helpers.
# ---------------------------------------------------------------------------
def existing_file(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"File not found: '{p}'")
    return p

# ---------------------------------------------------------------------------
# Build the CLI argument parser – options are added conditionally based on the
# presence of optional server scripts.
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("cli tool to decorate ollama cli and more..."),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model selection – optional, we may prompt later via fzf.
    model_arg = parser.add_argument(
        "-m",
        "--model",
        type=str,
        required=False,
        help="Name or identifier of the model to use.",
        metavar="MODEL",
    )
    # Autocomplete for model names when Ollama is reachable.
    def model_completer(prefix, **kwargs):
        try:
            models_info = ollama.list()
            return [m['model'] for m in models_info.get('models', []) if m['model'].startswith(prefix)]
        except Exception:
            return []
    model_arg.completer = model_completer

    # Load a previously saved chat file.
    parser.add_argument(
        "-l",
        "--load",
        type=existing_file,
        required=False,
        help="Path to a file that should be loaded.",
        metavar="CHAT",
    )

    # Various optional MCP feature flags – we enable them only if the relevant
    # server script exists in the repository.
    parser.add_argument(
        "--enable-fs",
        nargs='?',
        const='.',
        default=None,
        dest='enable_fs',
        help="Enable MCP file system tools in the specified directory (defaults to current directory).",
    )

    curr_dir = Path(__file__).parent

    if (curr_dir / "image_gen_server.py").exists():
        parser.add_argument("--enable-image", action='store_true', help="Enable MCP image generation tools.")
    if (curr_dir / "voice_server.py").exists():
        parser.add_argument("--enable-voice", action='store_true', help="Enable MCP voice/speech tools.")
    if (curr_dir / "multimedia_server.py").exists():
        parser.add_argument("--enable-webcam", action='store_true', help="Enable MCP webcam tools.")
        parser.add_argument("--enable-stt", "--enable-tss", action='store_true', help="Enable MCP speech-to-text tools.")
    if (curr_dir / "openshot_server.py").exists():
        parser.add_argument("--enable-video", action='store_true', help="Enable MCP video editing tools (OpenShot/FFmpeg).")
    if (curr_dir / "youtube_server.py").exists():
        parser.add_argument("--enable-youtube", action='store_true', help="Enable MCP YouTube search and transcript tools.")
    if (curr_dir / "konyks_server.py").exists():
        parser.add_argument("--enable-konyks", action='store_true', help="Enable MCP Konyks/Tuya smart home tools.")
    if (curr_dir / "spotify_server.py").exists():
        parser.add_argument("--enable-spotify", action='store_true', help="Enable MCP Spotify playback tools.")

    # Configuration convenience flags – do not require a server to be running.
    parser.add_argument("--config-spotify", action='store_true', help="Interactively setup Spotify API credentials in settings.json.")
    parser.add_argument("--config-konyks", action='store_true', help="Interactively setup Konyks (Tuya) API credentials in settings.json.")

    return parser

# ---------------------------------------------------------------------------
# Configuration helpers – interactive prompts that write to ``settings.json``.
# ---------------------------------------------------------------------------
async def setup_spotify_config(console, settings_dict, initial_arg=None):
    console.print("\n[bold cyan]Spotify Configuration[/bold cyan]")
    cid = settings_dict.get('SPOTIPY_CLIENT_ID', '')
    sec = settings_dict.get('SPOTIPY_CLIENT_SECRET', '')
    red = settings_dict.get('SPOTIPY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')

    if not initial_arg:
        cid = await asyncio.to_thread(prompt, "Enter SPOTIPY_CLIENT_ID: ", default=cid)
        sec = await asyncio.to_thread(prompt, "Enter SPOTIPY_CLIENT_SECRET: ", default=sec)
        red = await asyncio.to_thread(prompt, "Enter SPOTIPY_REDIRECT_URI: ", default=red)
        settings_dict['SPOTIPY_CLIENT_ID'] = cid.strip()
        settings_dict['SPOTIPY_CLIENT_SECRET'] = sec.strip()
        settings_dict['SPOTIPY_REDIRECT_URI'] = red.strip()
        save_settings(settings_dict)

    try:
        from spotipy.oauth2 import SpotifyOAuth
        scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-modify-public playlist-modify-private"
        cache_path = Path(__file__).parent / ".spotify_cache"
        auth_manager = SpotifyOAuth(
            client_id=settings_dict['SPOTIPY_CLIENT_ID'],
            client_secret=settings_dict['SPOTIPY_CLIENT_SECRET'],
            redirect_uri=settings_dict['SPOTIPY_REDIRECT_URI'],
            scope=scope,
            cache_path=str(cache_path),
            open_browser=False,
        )
        response_url = initial_arg
        if not response_url:
            auth_url = auth_manager.get_authorize_url()
            console.print(f"\n1. Please visit this URL in your browser:\n[bold cyan]{auth_url}[/bold cyan]")
            console.print("2. Log in and agree to permissions.")
            console.print("3. You will be redirected to your Redirect URI.")
            response_url = await asyncio.to_thread(prompt, "4. Paste the FULL URL or the CODE you were redirected to here: ")
        if response_url:
            response_url = response_url.strip()
            if not response_url.startswith("http"):
                code = response_url
            else:
                code = auth_manager.parse_response_code(response_url)
            token = auth_manager.get_access_token(code, as_dict=False)
            if token:
                console.print("[green]Authentication successful! Token saved.[/green]")
            else:
                console.print("[red]Failed to get access token.[/red]")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        console.print("[yellow]Tip: Make sure you copied the FULL URL or just the 'code=' part correctly.[/yellow]")
    console.print("[green]Spotify settings updated![/green]")

async def setup_konyks_config(console, settings_dict):
    console.print("\n[bold cyan]Konyks (Tuya) Configuration[/bold cyan]")
    cid = await asyncio.to_thread(prompt, "Enter TUYA_CLIENT_ID (Access ID): ", default=settings_dict.get('TUYA_CLIENT_ID', ''))
    sec = await asyncio.to_thread(prompt, "Enter TUYA_CLIENT_SECRET (Access Secret): ", default=settings_dict.get('TUYA_CLIENT_SECRET', ''))
    uid = await asyncio.to_thread(prompt, "Enter TUYA_UID (User ID): ", default=settings_dict.get('TUYA_UID', ''))
    reg = await asyncio.to_thread(prompt, "Enter TUYA_BASE_URL: ", default=settings_dict.get('TUYA_BASE_URL', 'https://openapi.tuyaeu.com'))
    settings_dict['TUYA_CLIENT_ID'] = cid.strip()
    settings_dict['TUYA_CLIENT_SECRET'] = sec.strip()
    settings_dict['TUYA_UID'] = uid.strip()
    settings_dict['TUYA_BASE_URL'] = reg.strip()
    save_settings(settings_dict)
    console.print("[green]Konyks settings saved![/green]")

# ---------------------------------------------------------------------------
# Helper for displaying the list of internal commands.
# ---------------------------------------------------------------------------
def show_internal_options(console):
    options = """
    Here are your options
    ---------------------
    exit => to quit
    /?   => to show this help
    /save => to save current CHAT
    /load => to load saved CHAT
    /settings => to show settings.json content and path
    !   => to run shell command (e.g. !ls)
    EOF => to valide prompt input
    >> => show all code blocks available
    >>0 => show code block 0 and add it to clipboard buffer
    || => show all tables available
    ||0 => show table 0 and add it to clipboard buffer
    << => toggle voice recording (requires --enable-tss)
    /config-spotify => setup Spotify API credentials
    /config-konyks => setup Konyks (Tuya) API credentials
    """
    console.print(options, style="red")

# ---------------------------------------------------------------------------
# Main asynchronous entry point – parses arguments, starts optional MCP servers,
# and runs the interactive REPL loop.
# ---------------------------------------------------------------------------
async def main_async(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)
    console = Console()

    # -------------------------------------------------------------------
    # Load an optional saved chat file.
    # -------------------------------------------------------------------
    messages: list[dict] = []
    buffer = ""
    model = None
    last_save_file = None
    auto_save_enabled = False

    if args.load:
        console.print(f"File to load:    {args.load}")
        try:
            c = ChatManager()
            c.load_from_file(str(args.load))
            model = c.get_model()
            loaded_history = c.data.get('history')
            if isinstance(loaded_history, str):
                messages = [{'role': 'user', 'content': loaded_history}]
            elif isinstance(loaded_history, list):
                messages = loaded_history
        except Exception as exc:
            console.print(f"Error reading file {args.load}: {exc}", file=sys.stderr)
            sys.exit(1)

    # -------------------------------------------------------------------
    # Configuration flags (Spotify / Konyks) – they run and then exit.
    # -------------------------------------------------------------------
    if args.config_spotify:
        await setup_spotify_config(console, settings)
        return 0
    if args.config_konyks:
        await setup_konyks_config(console, settings)
        return 0

    # -------------------------------------------------------------------
    # Model selection – either from CLI, from prior load, or via an interactive fzf.
    # -------------------------------------------------------------------
    if model is None:
        if args.model:
            model = args.model
        else:
            try:
                models_info = ollama.list()
                model_names = [m['model'] for m in models_info.get('models', [])]
                if not model_names:
                    raise ValueError("No models found in Ollama.")
                input_str = "\n".join(model_names)
                p = subprocess.Popen(['fzf'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                stdout, _ = p.communicate(input=input_str)
                selected = stdout.strip()
                if selected:
                    model = selected
                else:
                    raise ValueError("No model selected via fzf.")
            except Exception as e:
                raise ValueError(f"Model selection failed: {e}. Please specify --model.")
    console.print(f"Model selected:  {model}", style="bold white on green")

    # -------------------------------------------------------------------
    # Inner REPL – handles user input, EOF detection, internal commands,
    # streaming responses, and optional auto‑save.
    # -------------------------------------------------------------------
    async def run_loop(sessions=None):
        nonlocal buffer, messages, last_save_file, auto_save_enabled, model
        # Define a tiny completer that only offers completions at start‑of‑line.
        internal_commands = [
            'exit', '/?', '/save', '/load', '/settings', '/style', '/eof', '!', '/auto', 'EOF', '>>', '||', '<<',
            '/config-spotify', '/config-konyks'
        ]
        from prompt_toolkit.completion import Completion
        class StartOfLineCompleter(Completer):
            def get_completions(self, document, complete_event):
                if ' ' in document.text_before_cursor:
                    return
                for word in internal_commands:
                    if word.lower().startswith(document.text_before_cursor.lower()):
                        yield Completion(word, start_position=-len(document.text_before_cursor))
        completer = StartOfLineCompleter()
        session_input = PromptSession()
        is_recording = False
        mdl = None  # Will hold the last MarkdownExtractor instance.
        while True:
            prompt_text = f"{Emoji('peanuts')} >> {Emoji('brain')} \n" if not buffer else ""
            user_input = await session_input.prompt_async(
                prompt_text,
                style=style_b,
                completer=completer
            )
            # ----------------------------------------------------------------
            # Voice trigger handling (<< by default).
            # ----------------------------------------------------------------
            vt = settings.get('voice_trigger', '<<')
            if user_input.strip() == vt:
                if not sessions:
                    console.print("[red]Error: No MCP sessions active.[/red]")
                    continue
                # Find a session that provides a start_recording tool.
                stt_session = None
                for s in sessions:
                    try:
                        tools_res = await s.list_tools()
                        if any(t.name == "start_recording" for t in tools_res.tools):
                            stt_session = s
                            break
                    except Exception:
                        continue
                if not stt_session:
                    console.print("[red]Error: Speech‑to‑text server not active. Use --enable-tss.[/red]")
                    continue
                if not is_recording:
                    res = await stt_session.call_tool("start_recording", arguments={})
                    console.print(f"[bold green]{res.content[0].text}[/bold green]")
                    is_recording = True
                else:
                    console.print("[dim]Stopping recording and transcribing...[/dim]")
                    res = await stt_session.call_tool("stop_recording", arguments={})
                    if res.isError:
                        console.print(f"[red]Error stopping recording: {res.content[0].text}[/red]")
                    else:
                        transcribed_text = res.content[0].text
                        console.print(f"[bold cyan]Transcribed:[/] {transcribed_text}")
                        buffer += transcribed_text + " "
                    is_recording = False
                continue
            # ----------------------------------------------------------------
            # Internal command processing (exit, help, settings, etc.).
            # ----------------------------------------------------------------
            cmd = user_input.lower().strip()
            if cmd == 'exit':
                break
            if cmd == '/?':
                show_internal_options(console)
                continue
            if cmd == '/style':
                console.print("\n[bold cyan]Theme Customization[/bold cyan]")
                target = await asyncio.to_thread(prompt, "Change [b]lue or [g]reen style? (b/g): ", style=style_g)
                if target.lower() not in ['b', 'g']:
                    console.print("[red]Invalid selection.[/red]")
                    continue
                current = settings['style_b'] if target.lower() == 'b' else settings['style_g']
                console.print(f"Current color: {current}")
                new_color = await asyncio.to_thread(prompt, "Enter new style (e.g. '#ffffff bg:#ff0000'): ", style=style_g)
                if new_color:
                    try:
                        Style.from_dict({'': new_color})
                        if target.lower() == 'b':
                            settings['style_b'] = new_color
                            style_b = Style.from_dict({'': new_color})
                        else:
                            settings['style_g'] = new_color
                            style_g = Style.from_dict({'': new_color})
                        save_settings(settings)
                        console.print("[green]Style updated and saved![/green]")
                    except Exception as e:
                        console.print(f"[red]Error: Invalid style string. ({e})[/red]")
                continue
            if cmd == '/eof':
                console.print("\n[bold cyan]EOF Customization[/bold cyan]")
                console.print(f"Current EOF string: {settings.get('eof_string', 'EOF')}")
                new_eof = await asyncio.to_thread(prompt, "Enter new EOF string: ", style=style_g)
                if new_eof:
                    settings['eof_string'] = new_eof.strip()
                    save_settings(settings)
                    console.print(f"[green]EOF string updated to '{settings['eof_string']}' and saved![/green]")
                continue
            if cmd == '/settings':
                settings_path = Path(__file__).parent / "settings.json"
                console.print(f"\n[bold cyan]Settings Configuration[/bold cyan]")
                console.print(f"Path: [yellow]{settings_path}[/yellow]")
                if settings_path.exists():
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            console.print("\n" + f.read())
                    except Exception as e:
                        console.print(f"[red]Error reading settings file: {e}[/red]")
                else:
                    console.print("[yellow]Settings file does not exist yet (using defaults).[/yellow]")
                continue
            if cmd.startswith('/config-spotify'):
                arg = user_input.strip()[len('/config-spotify'):].strip()
                await setup_spotify_config(console, settings, initial_arg=arg)
                continue
            if cmd.startswith('/config-konyks'):
                await setup_konyks_config(console, settings)
                continue
            if user_input.startswith('!'):
                cmd = user_input[1:].strip()
                if not cmd:
                    console.print("[yellow]Usage: ! <command>[/yellow]")
                    continue
                try:
                    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                    if result.stdout:
                        console.print(result.stdout.strip())
                    if result.stderr:
                        console.print(f"[red]{result.stderr.strip()}[/red]")
                    if result.returncode != 0:
                        console.print(f"[bold red]Command exited with code {result.returncode}[/bold red]")
                except Exception as e:
                    console.print(f"[red]Error executing command: {e}[/red]")
                continue
            if cmd == '/save':
                chatname_input = await asyncio.to_thread(prompt, "enter the name of the chat to save:\n", style=style_g)
                c = ChatManager()
                c.save_file(chatname_input, model, messages)
                last_save_file = chatname_input
                continue
            if cmd == '/load':
                c = ChatManager()
                if not c.historyList:
                    console.print("[yellow]No saved chats found in .historyList.json.[/yellow]")
                    continue
                try:
                    display = [f"{item['fileName']} ({item['path']})" for item in c.historyList]
                    p = subprocess.Popen(['fzf', '--prompt=Select chat to load: '], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                    stdout, _ = p.communicate('\n'.join(display))
                    selected = stdout.strip()
                    if selected:
                        sel_item = next((it for it in c.historyList if f"{it['fileName']} ({it['path']})" == selected), None)
                        if sel_item:
                            c.load_from_file(sel_item['path'])
                            model = c.get_model()
                            hist = c.data.get('history')
                            messages = [{'role': 'user', 'content': hist}] if isinstance(hist, str) else (hist or [])
                            last_save_file = sel_item['fileName']
                            console.print(f"[green]Successfully loaded chat: {sel_item['fileName']}[/green]")
                            console.print(f"Active model: [bold]{model}[/bold]")
                        else:
                            console.print("[red]Could not match selection to history list.[/red]")
                    else:
                        console.print("[yellow]Load cancelled.[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error during load: {e}[/red]")
                continue
            if cmd == '/auto':
                if not last_save_file:
                    console.print("[yellow]You must use /save at least once before enabling auto-save.[/yellow]")
                else:
                    auto_save_enabled = not auto_save_enabled
                    status = "[green]enabled[/green]" if auto_save_enabled else "[red]disabled[/red]"
                    console.print(f"Auto-save to [bold]{last_save_file}[/bold] is now {status}.")
                continue
            if user_input.startswith('>>'):
                if mdl is None:
                    console.print("[yellow]No response generated yet to extract from.[/yellow]")
                    continue
                idx_part = user_input[2:].strip()
                if not idx_part:
                    mdl.print_code_blocks()
                else:
                    try:
                        idx = int(idx_part)
                        mdl.print_code(idx)
                        blocks = mdl.extract_code_blocks()
                        if 0 <= idx < len(blocks):
                            pyperclip.copy(blocks[idx]['code'])
                            console.print("[dim]Code copied to clipboard.[/dim]")
                    except ValueError:
                        console.print("[red]Invalid index for >> command.[/red]")
                continue
            if user_input.startswith('||'):
                if mdl is None:
                    console.print("[yellow]No response generated yet to extract from.[/yellow]")
                    continue
                idx_part = user_input[2:].strip()
                if not idx_part:
                    mdl.print_tables()
                else:
                    try:
                        idx = int(idx_part)
                        mdl.print_table(idx)
                        tables = mdl.extract_tables()
                        if 0 <= idx < len(tables):
                            pyperclip.copy(tables[idx])
                            console.print("[dim]Table copied to clipboard.[/dim]")
                    except ValueError:
                        console.print("[red]Invalid index for || command.[/red]")
                continue
            # ----------------------------------------------------------------
            # Regular user text – accumulate until EOF marker is seen.
            # ----------------------------------------------------------------
            buffer += user_input
            eof_marker = settings.get('eof_string', 'EOF')
            if eof_marker in buffer:
                content, _, _ = buffer.partition(eof_marker)
                messages.append({'role': 'user', 'content': content})
                buffer = ""
                # ----------------------------------------------------------------
                # Stream the assistant response with live markdown rendering.
                # ----------------------------------------------------------------
                current_response = ""
                with Live(console=console, refresh_per_second=10, transient=False) as live:
                    async for token in run_chat_turn(model, messages, sessions):
                        current_response += token
                        try:
                            md = Markdown(current_response)
                        except Exception:
                            md = Text(current_response)
                        live.update(md)
                mdl = MarkdownExtractor(current_response)
                console.print("\n")
                # Auto‑save if enabled.
                if auto_save_enabled and last_save_file:
                    try:
                        c = ChatManager()
                        c.save_file(last_save_file, model, messages)
                        console.print(f"[dim italic]Auto-saved to {last_save_file}[/dim italic]")
                    except Exception as e:
                        console.print(f"[red]Auto-save failed: {e}[/red]")
    # -------------------------------------------------------------------
    # Spin up optional MCP servers based on parsed arguments.
    # -------------------------------------------------------------------
    active_sessions = []
    from contextlib import AsyncExitStack
    async with AsyncExitStack() as stack:
        # Helper to start a server and register its session.
        async def start_server(script_name: str, extra_args: list[str] = []):
            server_path = Path(__file__).parent / script_name
            params = StdioServerParameters(command=sys.executable, args=[str(server_path)] + extra_args)
            try:
                read, write = await stack.enter_async_context(stdio_client(params))
                sess = await stack.enter_async_context(ClientSession(read, write))
                await sess.initialize()
                active_sessions.append(sess)
            except Exception as e:
                console.print(f"[bold red]Error:[/] {script_name} failed: {e}")

        if getattr(args, 'enable_fs', False):
            await start_server("simple_fs_server.py", [str(args.enable_fs)])
        if getattr(args, 'enable_image', False):
            await start_server("image_gen_server.py")
        if getattr(args, 'enable_voice', False):
            await start_server("voice_server.py")
        if getattr(args, 'enable_webcam', False) or getattr(args, 'enable_stt', False):
            await start_server("multimedia_server.py")
        if getattr(args, 'enable_video', False):
            await start_server("openshot_server.py")
        if getattr(args, 'enable_youtube', False):
            await start_server("youtube_server.py")
        # Konyks – auto‑enable if credentials are present.
        enable_konyks = getattr(args, 'enable_konyks', False)
        if not enable_konyks and settings.get('TUYA_CLIENT_ID') and (Path(__file__).parent / "konyks_server.py").exists():
            enable_konyks = True
        if enable_konyks:
            await start_server("konyks_server.py")
        # Spotify – auto‑enable if credentials are present.
        enable_spotify = getattr(args, 'enable_spotify', False)
        if not enable_spotify and settings.get('SPOTIPY_CLIENT_ID') and (Path(__file__).parent / "spotify_server.py").exists():
            enable_spotify = True
        if enable_spotify:
            await start_server("spotify_server.py")

        await run_loop(active_sessions if active_sessions else None)
    return 0

# ---------------------------------------------------------------------------
# Entry‑point wrapper.
# ---------------------------------------------------------------------------
def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
