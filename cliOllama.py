import re
import json
import argparse
import pyperclip
import subprocess
from pathlib import Path
from rich.text import Text
from rich.live import Live
from rich.emoji import Emoji
from rich.console import Console
from prompt_toolkit import prompt
from rich.markdown import Markdown
from typing import Any, Dict, Union 
from prompt_toolkit.styles import Style
from MarkedownExtractor import MarkdownExtractor


# define style for prompt
style_b = Style.from_dict({
    '': '#ffffff bg:#0e49ba',  # Blue text
})
style_g = Style.from_dict({
    '': '#ffffff bg:green',  # Green text
})

# call to ollama subprocess
def run_ollama_cli(model: str, history: str):
    try:
        p = subprocess.Popen(
            ['ollama', 'run', model, "--hidethinking", "--think=false"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line-buffered
        )

        p.stdin.write(history)
        p.stdin.flush()
        p.stdin.close()

        # Stream output
        while True:
            line = p.stdout.readline()
            if not line:
                break
            yield line

        ## Check for errors
        #stderr_output = p.stderr.read()
        #if stderr_output:
        #    yield f"{stderr_output}"

        p.wait()

    except Exception as e:
        yield f"Internal ERROR: {str(e)}"


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
    """
    console.print(options, style="red")

class ChatMangager:
    def __init__():
        pass

    def load_from_file(cls, file_path: Union[str, Path]) -> json:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise ChatManagerError(f"File not found: {path}")
        try:
            raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ChatManagerError(f"Invalid JSON in {path}: {exc}") from exc



########
# MAIN #
########
def main(argv: list[str] | None = None) -> int:

    # Init parser
    parser = build_parser()
    args = parser.parse_args(argv)
    # Init console
    console = Console()

    # Init values
    history = ""
    buffer = ""
    mdl=None
    model=None

    # Parse cli arguments
    if args.model:
        model=args.model
    else:
        cmd="echo -n $(ollama list | fzf --tac |awk '{print $1}')"
        model=subprocess.check_output(['bash',  '-c', cmd]).decode()
    console.print(f"Model selected:  {model}", style="bold white on green")

    if args.load:
        console.print(f"File to load:    {args.load}")
        # Example of opening the file safely:
        try:
            with args.load.open("r", encoding="utf-8") as f:
                content = f.read()
                console.print(f"First 200 chars of the file:\n{content[:200]!r}")
        except Exception as exc:
            console.print(f"Error reading file {args.load}: {exc}", file=sys.stderr)
            sys.exit(1)

    # Main loop
    while True:
        user_input = prompt(f"{Emoji('peanuts')} >> {Emoji('brain')} \n", style=style_b) if not buffer else prompt("", style=style_b)

        if user_input.lower() == 'exit':
            break
        if user_input.lower() == '/?':
            show_internal_options(console)
            user_input=""
            pass
        if user_input.lower() == '/save':
            chatname_input = prompt("enter the name of the chat to save:\n",style=style_g)
            console.print(chatname_input)
            user_input=""
            pass
        if user_input.lower() == '/load':
            chatname_input = prompt("enter the name of the chat to load:\n",style=style_g)
            console.print(chatname_input)
            user_input=""
            pass
        match1 = re.match(r'(>>\ *)([0-9]+)(.*)', user_input)
        if match1 and mdl:
            number=match1.group(2)
            console.print(number)
            mdl.print_code(int(number))
            try:
                pyperclip.copy(mdl.extract_all().get("code_blocks")[int(number)].get('code'))
            except:
                pass
            user_input=""
            pass
        match2 = re.match(r'(||\ *)([0-9]+)(.*)', user_input)
        if match2 and mdl:
            number=match2.group(2)
            console.print(number)
            mdl.print_table(int(number))
            try:
                pyperclip.copy(mdl.extract_all().get("tables")[int(number)].get('code'))
            except:
                pass
            user_input=""
            pass

        buffer += user_input

        if "EOF" in buffer:
            content, _, _ = buffer.partition("EOF")
            history += f"\nUser: {content}"
            buffer = ""

            # Print user input
            console.print(f"[bold cyan]User:[/bold cyan] {content}\n")

            # Stream assistant response
            current_response = ""
            with Live(console=console, refresh_per_second=10, transient=False) as live:
                for line in run_ollama_cli(model, history):
                    current_response += line
                    # Try to render as markdown
                    try:
                        md = Markdown(current_response)
                    except Exception:
                        md = Text(current_response)
                    live.update(md)
                    history += f"\nModel:{line}"
                mdl=MarkdownExtractor(current_response)

            console.print("\n")  # Add spacing between interactions

if __name__ == "__main__":
    main()

