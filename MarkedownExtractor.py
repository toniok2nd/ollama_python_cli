from typing import List, Dict, Optional
from rich.console import Console
import re

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


