from typing import List, Dict, Optional
from rich.markdown import Markdown
from rich.console import Console
import re

class MarkdownExtractor:
    """
    Utility class to parse and extract structured elements (tables and code blocks) 
    from a Markdown string. It allows for selective rendering using the Rich library.
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
        """
        Initialize the extractor with markdown text.
        
        Args:
            markdown_text: The raw markdown string to parse.
        """
        self.text = markdown_text
        self.console = Console()

        # Cache parsed data for performance
        self._tables = None
        self._code_blocks = None

    # ---------------- Extraction ---------------- #

    def extract_code_blocks(self) -> List[Dict[str, Optional[str]]]:
        """
        Identifies and extracts all fenced code blocks from the text.
        
        Returns:
            A list of dictionaries, each containing 'language' and 'code'.
        """
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
        """
        Identifies and extracts all Markdown tables from the text.
        Uses a heuristic to ensure the extracted block contains a separator line.
        
        Returns:
            A list of raw table strings.
        """
        if self._tables is not None:
            return self._tables

        tables = []
        for match in self._table_pattern.finditer(self.text):
            table = match.group(1).strip()
            # Simple check for the separator line (e.g., |---|)
            if re.search(r'\|\s*:?-{3,}:?\s*\|', table):
                tables.append(table)
        self._tables = tables
        return tables

    def extract_all(self) -> Dict[str, List]:
        """
        Extracts both tables and code blocks.
        
        Returns:
            A dictionary with 'tables' and 'code_blocks' keys.
        """
        return {
            'tables': self.extract_tables(),
            'code_blocks': self.extract_code_blocks(),
        }

    # ---------------- Rendering ---------------- #

    def print_table(self, index: int):
        """
        Renders a specific extracted table to the console using Rich.
        
        Args:
            index: The 0-based index of the table to print.
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
        Renders a specific extracted code block to the console using Rich.
        
        Args:
            index: The 0-based index of the code block to print.
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
        """Renders all found tables to the console."""
        tables = self.extract_tables()
        if not tables:
            self.console.print("[yellow]No tables found.[/yellow]")
            return

        for i in range(0, len(tables)):
            self.print_table(i)

    def print_code_blocks(self):
        """Renders all found code blocks to the console."""
        blocks = self.extract_code_blocks()
        if not blocks:
            self.console.print("[yellow]No code blocks found.[/yellow]")
            return

        for i in range(0, len(blocks)):
            self.print_code(i)

    def print_all(self):
        """Renders everything extracted (tables and code) to the console."""
        self.console.print("\n[bold cyan]Extracted Tables:[/bold cyan]")
        self.print_tables()
        self.console.print("\n[bold cyan]Extracted Code Blocks:[/bold cyan]")
        self.print_code_blocks()
