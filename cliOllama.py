from mcp import ClientSession, StdioServerParameters
from prompt_toolkit.completion import WordCompleter, Completer
from markedownExtractor import MarkdownExtractor
from mcp.client.stdio import stdio_client
from prompt_toolkit.styles import Style
from mcp.types import CallToolResult
from typing import Any, Dict, Union 
from chatManager import ChatManager
from rich.markdown import Markdown
from prompt_toolkit import prompt
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


# Default settings and style management
def load_settings():
    settings_path = Path(__file__).parent / "settings.json"
    defaults = {
        "style_b": "#ffffff bg:#0e49ba",
        "style_g": "#ffffff bg:green",
        "eof_string": "EOF"
    }
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return {**defaults, **json.load(f)}
        except Exception:
            return defaults
    return defaults

def save_settings(settings_dict):
    settings_path = Path(__file__).parent / "settings.json"
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}", file=sys.stderr)

# Initialize settings and styles
settings = load_settings()
style_b = Style.from_dict({'': settings['style_b']})
style_g = Style.from_dict({'': settings['style_g']})

async def run_chat_turn(model, messages, session=None):
    """Run a single turn of chat, handling tool calls if session is provided."""
    
    # Get available tools if session is present
    tools = []
    if session:
        result = await session.list_tools()
        # Convert MCP tools to Ollama tool format
        for tool in result.tools:
            tools.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.inputSchema
                }
            })

    
    # We will use a dedicated loop for the tool-calling cycle
    while True:
        # Call Ollama
        # Note: ollama.chat returns an iterator if stream=True
        stream = ollama.chat(model=model, messages=messages, tools=tools if tools else None, stream=True)
        
        final_message = {'role': 'assistant', 'content': '', 'tool_calls': []}
        
        for chunk in stream:
            # Handle content
            content = chunk.get('message', {}).get('content', '')
            if content:
                final_message['content'] += content
                yield content

            # Handle tool calls (accumulate)
            if 'tool_calls' in chunk.get('message', {}):
                # This assumes tool_calls come in one chunk or need merging. 
                # Ollama python lib might normalize this?
                # Actually, standard behavior is full tool call in one message or accumulated.
                # Let's accumulate. 
                tcs = chunk['message']['tool_calls']
                for tc in tcs:
                     # Convert to dict to ensure JSON serializability
                     if hasattr(tc, 'model_dump'):
                         final_message['tool_calls'].append(tc.model_dump())
                     elif hasattr(tc, 'dict'):
                         final_message['tool_calls'].append(tc.dict())
                     else:
                         # Fallback manual extraction
                         final_message['tool_calls'].append({
                             'type': 'function',
                             'function': {
                                 'name': getattr(tc.function, 'name', None),
                                 'arguments': getattr(tc.function, 'arguments', None)
                             }
                         })

        # After stream finishes
        if not final_message['tool_calls']:
            del final_message['tool_calls']
        messages.append(final_message)

        if not final_message.get('tool_calls'):
            break # No tools called, we are done
        
        # We have tool calls
        if not session:
            yield "\n[Error: Tool called but no MCP session active]"
            break

        # Execute tools
        for tool_call in final_message['tool_calls']:
            fn_name = tool_call['function']['name']
            fn_args = tool_call['function']['arguments']
            yield f"\n[Executing tool: {fn_name}...]"
            
            try:
                # Call MCP tool
                result = await session.call_tool(fn_name, arguments=fn_args)
                
                # Extract text tool output robustly
                tool_output = ""
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        tool_output += content_item.text
                    elif isinstance(content_item, dict) and 'text' in content_item:
                        tool_output += content_item['text']
                
                # Append tool result to messages with correlation name
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
        
        # Loop back to send tool results to model and get next response




def existing_file(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"File not found: '{p}'")
    return p


def build_parser() -> argparse.ArgumentParser:
    """
    Construct the ArgumentParser with the desired options.

    Returns
    -------
    argparse.ArgumentParser
        Fully configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "cli tool to decorate ollama cli and more..."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # -m / --model   : a free‑form string (e.g. "resnet50", "my_custom_model")
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        required=False,          # change to True if the model name must be supplied
        help="Name or identifier of the model to use.",
        metavar="MODEL",
    )

    # -l / --load   : a file path that must exist on the filesystem
    parser.add_argument(
        "-l",
        "--load",
        type=existing_file,      # uses the helper above to validate existence
        required=False,          # change to True if the file is mandatory
        help="Path to a file that should be loaded.",
        metavar="CHAT",
    )

    parser.add_argument(
        "--enable-fs",
        nargs='?',
        const='.',
        default=None,
        dest='enable_fs',
        help="Enable MCP file system tools in the specified directory (defaults to current directory).",
    )

    return parser

# define internal options
def show_internal_options(console):
    options="""
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
    """
    console.print(options, style="red")

########
# MAIN #
########
async def main_async(argv: list[str] | None = None) -> int:
    # Init parser
    parser = build_parser()
    args = parser.parse_args(argv)
    # Init console
    console = Console()

    # Init values
    messages = []
    buffer = ""
    mdl=None
    model=None

    # Parse args (load logic)
    if args.load:
        console.print(f"File to load:    {args.load}")
        try:
            c=ChatManager()
            c.load_from_file(str(args.load))
            model=c.get_model()
            # Convert loaded string history to messages if needed
            loaded_history = c.data.get('history')
            if isinstance(loaded_history, str):
                # Legacy: treat as one big system/user prompt? Or just start fresh?
                # Let's inject it as a first user message for context
                messages = [{'role': 'user', 'content': loaded_history}]
            elif isinstance(loaded_history, list):
                messages = loaded_history
        except Exception as exc:
            console.print(f"Error reading file {args.load}: {exc}", file=sys.stderr)
            sys.exit(1)

    if model is None:
        if args.model:
            model = args.model
        else:
            # Interactive selection logic
            try:
                models_info = ollama.list()
                model_names = [m['model'] for m in models_info.get('models', [])]
                if not model_names:
                     raise ValueError("No models found inb Ollama.")
                input_str = '\n'.join(model_names)
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

    # Define the input loop function
    async def run_loop(session=None):
        global style_b, style_g, settings
        nonlocal buffer, messages, mdl, model
        last_save_file = None
        auto_save_enabled = False
        
        # Internal commands for autocompletion
        internal_commands = [
            'exit', '/?', '/save', '/load', '/settings', '/style', '/eof', '!', '/auto', 'EOF', '>>', '||'
        ]
        
        class StartOfLineCompleter(Completer):
            def __init__(self, words):
                self.word_completer = WordCompleter(words, ignore_case=True)
            def get_completions(self, document, complete_event):
                # Only offer completions if we're at the very start of the line
                # (allowing for leading whitespace if desired, but here we strictly check for no preceding spaces)
                if ' ' in document.text_before_cursor:
                    return
                yield from self.word_completer.get_completions(document, complete_event)

        completer = StartOfLineCompleter(internal_commands)

        while True:
            # We use prompt() synchronously because it's blocking anyway
            # But inside async function, should we use run_in_executor?
            # Creating a prompt session might be better, but sticking to existing prompt()
            # method which blocks the event loop is OK if no background tasks.
            # However, prompt() returns a string.
            
            user_input = await asyncio.to_thread(
                prompt, 
                f"{Emoji('peanuts')} >> {Emoji('brain')} \n" if not buffer else "", 
                style=style_b,
                completer=completer
            )

            if user_input.lower() == 'exit':
                break
            if user_input.lower() == '/?':
                show_internal_options(console)
                continue
            if user_input.lower() == '/style':
                console.print("\n[bold cyan]Theme Customization[/bold cyan]")
                target = await asyncio.to_thread(prompt, "Change [b]lue or [g]reen style? (b/g): ", style=style_g)
                if target.lower() not in ['b', 'g']:
                    console.print("[red]Invalid selection.[/red]")
                    continue
                
                current_color = settings['style_b'] if target.lower() == 'b' else settings['style_g']
                console.print(f"Current color: {current_color}")
                new_color = await asyncio.to_thread(prompt, "Enter new style (e.g. '#ffffff bg:#ff0000'): ", style=style_g)
                
                if new_color:
                    try:
                        # Test if style is valid
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
                        console.print(f"[red]Error: Invalid style string format. ({e})[/red]")
                continue

            if user_input.lower() == '/eof':
                console.print("\n[bold cyan]EOF Customization[/bold cyan]")
                console.print(f"Current EOF string: {settings.get('eof_string', 'EOF')}")
                new_eof = await asyncio.to_thread(prompt, "Enter new EOF string: ", style=style_g)
                if new_eof:
                    settings['eof_string'] = new_eof.strip()
                    save_settings(settings)
                    console.print(f"[green]EOF string updated to '{settings['eof_string']}' and saved![/green]")
                continue

            if user_input.lower() == '/settings':
                settings_path = Path(__file__).parent / "settings.json"
                console.print(f"\n[bold cyan]Settings Configuration[/bold cyan]")
                console.print(f"Path: [yellow]{settings_path}[/yellow]")
                if settings_path.exists():
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            console.print("\n" + content)
                    except Exception as e:
                        console.print(f"[red]Error reading settings file: {e}[/red]")
                else:
                    console.print("[yellow]Settings file does not exist yet (using defaults).[/yellow]")
                continue

            if user_input.startswith('!'):
                cmd = user_input[1:].strip()
                if not cmd:
                    console.print("[yellow]Usage: ! <command>[/yellow]")
                    continue
                try:
                    # Run the command and capture output
                    # We use shell=True to allow piping and expansions
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

            if user_input.lower() == '/save':
                chatname_input = await asyncio.to_thread(prompt, "enter the name of the chat to save:\n", style=style_g)
                c=ChatManager()
                c.save_file(chatname_input, model, messages)
                last_save_file = chatname_input
                continue

            if user_input.lower() == '/load':
                c = ChatManager()
                if not c.historyList:
                    console.print("[yellow]No saved chats found in .historyList.json.[/yellow]")
                    continue
                
                # Prepare list for fzf
                # historyList elements: {"fileName": "...", "path": "..."}
                try:
                    display_names = [f"{item['fileName']} ({item['path']})" for item in c.historyList]
                    input_str = '\n'.join(display_names)
                    
                    p = subprocess.Popen(['fzf', '--prompt=Select chat to load: '], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                    stdout, _ = p.communicate(input=input_str)
                    selected_line = stdout.strip()
                    
                    if selected_line:
                        # Extract fileName (it's before the first space and parenthesis)
                        # More robust: find the matching item in historyList
                        selected_item = next((item for item in c.historyList if f"{item['fileName']} ({item['path']})" == selected_line), None)
                        
                        if selected_item:
                            selected_path = selected_item['path']
                            c.load_from_file(selected_path)
                            model = c.get_model()
                            
                            loaded_history = c.data.get('history')
                            if isinstance(loaded_history, str):
                                messages = [{'role': 'user', 'content': loaded_history}]
                            elif isinstance(loaded_history, list):
                                messages = loaded_history
                            
                            last_save_file = selected_item['fileName']
                            console.print(f"[green]Successfully loaded chat: {selected_item['fileName']}[/green]")
                            console.print(f"Active model: [bold]{model}[/bold]")
                        else:
                            console.print("[red]Could not match selection to history list.[/red]")
                    else:
                        console.print("[yellow]Load cancelled.[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error during load: {e}[/red]")
                continue

            if user_input.lower() == '/auto':
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
                cmd_val = user_input[2:].strip()
                if not cmd_val:
                    mdl.print_code_blocks()
                else:
                    try:
                        idx = int(cmd_val)
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
                cmd_val = user_input[2:].strip()
                if not cmd_val:
                    mdl.print_tables()
                else:
                    try:
                        idx = int(cmd_val)
                        mdl.print_table(idx)
                        tables = mdl.extract_tables()
                        if 0 <= idx < len(tables):
                            pyperclip.copy(tables[idx])
                            console.print("[dim]Table copied to clipboard.[/dim]")
                    except ValueError:
                        console.print("[red]Invalid index for || command.[/red]")
                continue
            
            buffer += user_input

            eof_marker = settings.get('eof_string', 'EOF')
            if eof_marker in buffer:
                content, _, _ = buffer.partition(eof_marker)
                messages.append({'role': 'user', 'content': content})
                buffer = ""

                current_response = ""
                with Live(console=console, refresh_per_second=10, transient=False) as live:
                    # Async generator iteration
                    async for token in run_chat_turn(model, messages, session):
                        current_response += token
                        try:
                            md = Markdown(current_response)
                        except Exception:
                            md = Text(current_response)
                        live.update(md)
                    
                mdl=MarkdownExtractor(current_response)
                console.print("\n")

                if auto_save_enabled and last_save_file:
                    try:
                        c = ChatManager()
                        c.save_file(last_save_file, model, messages)
                        console.print(f"[dim italic]Auto-saved to {last_save_file}[/dim italic]")
                    except Exception as e:
                        console.print(f"[red]Auto-save failed: {e}[/red]")

    # Entry point logic
    if args.enable_fs:
        server_path = Path(__file__).parent / "simple_fs_server.py"
        # Pass the workdir as an argument to the server script
        server_params = StdioServerParameters(command="python", args=[str(server_path), str(args.enable_fs)])
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await run_loop(session)
    else:
        await run_loop(None)

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()

