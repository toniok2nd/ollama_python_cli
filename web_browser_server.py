import sys
import os
import subprocess
import asyncio
import json
import re
from typing import List

import requests
from bs4 import BeautifulSoup

from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    CallToolResult,
)
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Compress whitespace and strip leading/trailing spaces."""
    return re.sub(r"\s+", " ", text).strip()

def _search_duckduckgo(query: str, limit: int = 5) -> List[dict]:
    """Simple DuckDuckGo HTML search scraper.

    Returns a list of dicts with keys: title, url, snippet.
    No API key required.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WebBrowserMCP/0.1; +https://github.com/yourrepo)"
    }
    params = {"q": query, "kl": "wt-wt"}  # English results
    resp = requests.get("https://duckduckgo.com/html/", params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[dict] = []
    for result in soup.select("div.result")[:limit]:
        a = result.select_one("a.result__a")
        if not a:
            continue
        title = _clean_text(a.get_text())
        url = a["href"]
        snippet_el = result.select_one("a.result__snippet") or result.select_one("div.result__snippet")
        snippet = _clean_text(snippet_el.get_text()) if snippet_el else ""
        results.append({"title": title, "url": url, "snippet": snippet})
    return results

def _fetch_page(url: str) -> str:
    """Retrieve the main textual content of a web page.

    Scripts, styles and noscript tags are stripped.
    Raises ``requests.RequestException`` on network errors.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; WebBrowserMCP/0.1; +https://github.com/yourrepo)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return _clean_text(text)

# ---------------------------------------------------------------------------
# MCP server definition
# ---------------------------------------------------------------------------

server = Server("web-browser-mcp-server")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """Expose two tools: ``search_web`` and ``fetch_page``."""
    return [
        Tool(
            name="search_web",
            description="Search the web for a query and return a short list of titles, URLs and snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="fetch_page",
            description="Fetch the main readable text of a web page given its URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "format": "uri", "description": "Full URL to retrieve"},
                },
                "required": ["url"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> CallToolResult:
    if not arguments:
        return CallToolResult(content=[TextContent(type="text", text="Error: No arguments supplied")], isError=True)

    if name == "search_web":
        query = arguments.get("query")
        limit = int(arguments.get("limit", 5))
        try:
            results = _search_duckduckgo(query, limit)
            if not results:
                return CallToolResult(content=[TextContent(type="text", text="No results found.")])
            lines = []
            for r in results:
                lines.append(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}\n---")
            return CallToolResult(content=[TextContent(type="text", text="\n".join(lines))])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error during search: {e}")], isError=True)

    elif name == "fetch_page":
        url = arguments.get("url")
        try:
            page_text = _fetch_page(url)
            max_len = 2000
            if len(page_text) > max_len:
                page_text = page_text[:max_len] + "... (truncated)"
            return CallToolResult(content=[TextContent(type="text", text=page_text)])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error fetching page: {e}")], isError=True)
    else:
        return CallToolResult(content=[TextContent(type="text", text=f"Unknown tool: {name}")], isError=True)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="web-browser-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    # Cleaner pattern to discard noisy stdout (e.g., welcome banners).
    if os.environ.get("MCP_CLEANER_OK") != "TRUE":
        env = os.environ.copy()
        env["MCP_CLEANER_OK"] = "TRUE"
        proc = subprocess.Popen([sys.executable] + sys.argv, stdout=subprocess.PIPE, stdin=sys.stdin, stderr=sys.stderr, env=env)
        for line in proc.stdout:
            stripped = line.strip()
            if stripped.startswith(b"{"):
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            elif stripped:
                sys.stderr.buffer.write(b"[DEBUG] Discarded noise: " + line)
                sys.stderr.flush()
        sys.exit(proc.wait())
    else:
        asyncio.run(main())
