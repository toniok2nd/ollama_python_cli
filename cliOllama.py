import subprocess
import re
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from prompt_toolkit.styles import Style
from rich.emoji import Emoji
from prompt_toolkit import prompt


import pyperclip

from typing import List, Dict, Optional

class MarkdownExtractor:
    """
    Extracts Markdown tables and code zones from a Markdown string,
    and allows selective rendering with Rich.
    """

    _code_block_pattern = re.compile(
        r"```(?P<lang>[a-zA-Z0-9_-]*)\n(?P<code>.*?)```",
        re.DOTALL
    )

    _table_pattern = re.compile(
        r"((?:\|.*?\|\n)+)",  # multiple lines of a Markdown table
        re.MULTILINE
    )

    def __init__(self, markdown_text: str):
        self.text = markdown_text
        self.console = Console()

        # Cache parsed data
        self._tables = None
        self._code_blocks = None

    # ---------------- Extraction ---------------- #

    def extract_code_blocks(self) -> List[Dict[str, Optional[str]]]:
        """Extract all fenced code blocks."""
        if self._code_blocks is not None:
            return self._code_blocks

        blocks = []
        for match in self._code_block_pattern.finditer(self.text):
            lang = match.group('lang').strip() or None
            code = match.group('code').strip()
            blocks.append({'language': lang, 'code': code})
        self._code_blocks = blocks
        return blocks

    def extract_tables(self) -> List[str]:
        """Extract all Markdown tables as raw text."""
        if self._tables is not None:
            return self._tables

        tables = []
        for match in self._table_pattern.finditer(self.text):
            table = match.group(1).strip()
            if re.search(r'\|\s*:?-{3,}:?\s*\|', table):
                tables.append(table)
        self._tables = tables
        return tables

    def extract_all(self) -> Dict[str, List]:
        """Return both tables and code blocks."""
        return {
            'tables': self.extract_tables(),
            'code_blocks': self.extract_code_blocks(),
        }

    # ---------------- Rendering ---------------- #

    def print_table(self, index: int):
        """
        Print a specific table by index (1-based).
        """
        tables = self.extract_tables()
        if not tables:
            self.console.print("[yellow]No tables found.[/yellow]")
            return
        if not (0 <= index <= len(tables)-1):
            self.console.print(f"[red]Invalid table index:[/red] {index}")
            return

        table_text = tables[index]
        self.console.rule(f"📊 Table {index}")
        self.console.print(Markdown(table_text))

    def print_code(self, index: int):
        """
        Print a specific code block by index (1-based).
        """
        blocks = self.extract_code_blocks()
        if not blocks:
            self.console.print("[yellow]No code blocks found.[/yellow]")
            return
        if not (0 <= index <= len(blocks)-1):
            self.console.print(f"[red]Invalid code block index:[/red] {index}")
            return

        block = blocks[index]
        lang = block['language'] or 'text'
        self.console.rule(f"💻 Code Block {index} ({lang})")
        md = Markdown(f"```{lang}\n{block['code']}\n```")
        self.console.print(md)

    def print_tables(self):
        """Print all tables."""
        tables = self.extract_tables()
        if not tables:
            self.console.print("[yellow]No tables found.[/yellow]")
            return

        for i in range(0, len(tables)):
            self.print_table(i)

    def print_code_blocks(self):
        """Print all code blocks."""
        blocks = self.extract_code_blocks()
        if not blocks:
            self.console.print("[yellow]No code blocks found.[/yellow]")
            return

        for i in range(0, len(blocks)):
            self.print_code(i)

    def print_all(self):
        """Print everything."""
        self.console.print("\n[bold cyan]Extracted Tables:[/bold cyan]")
        self.print_tables()
        self.console.print("\n[bold cyan]Extracted Code Blocks:[/bold cyan]")
        self.print_code_blocks()


style = Style.from_dict({
    '': '#ffffff bg:#0e49ba',  # Blue text
})

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

def main():
    model = 'minimax-m2:cloud'
    console = Console()
    history = ""
    buffer = ""
    mdl=None

    while True:
        user_input = prompt(f"{Emoji('peanuts')} >> {Emoji('brain')} \n", style=style) if not buffer else prompt("", style=style)

        if user_input.lower() == 'exit':
            break
        match1 = re.match(r'(>>\ *)([0-9]+)(.*)', user_input)
        if match1 and mdl:
            number=match1.group(2)
            print(number)
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
            print(number)
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

