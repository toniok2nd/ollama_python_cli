try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Web Browser Server")
except:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("Web Browser Server")

import sys
import os
import subprocess
import asyncio
import json
import re
from typing import List

import requests
from bs4 import BeautifulSoup

# Note: The original server used lower-level mcp.server.Server and stdio_server.
# To align with the FastMCP pattern in simple_fs_server.py, we migrate the tools here.

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
# MCP tool definitions using the unified mcp object
# ---------------------------------------------------------------------------

@mcp.tool()
def search_web(query: str, limit: int = 5) -> str:
    """Search the web for a query and return a short list of titles, URLs and snippets."""
    try:
        results = _search_duckduckgo(query, limit)
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}\n---")
        return "\n".join(lines)
    except Exception as e:
        return f"Error during search: {e}"

@mcp.tool()
def fetch_page(url: str) -> str:
    """Fetch the main readable text of a web page given its URL."""
    try:
        page_text = _fetch_page(url)
        max_len = 2000
        if len(page_text) > max_len:
            page_text = page_text[:max_len] + "... (truncated)"
        return page_text
    except Exception as e:
        return f"Error fetching page: {e}"

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
        mcp.run(transport='stdio')
