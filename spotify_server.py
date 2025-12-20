import asyncio
import os
import json
import sys
import webbrowser
from typing import Any, Dict, List, Optional
from pathlib import Path

# Check for spotipy
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    spotipy = None

from mcp.server.stdio import stdio_server
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    CallToolResult,
)

# Initialize MCP Server
server = Server("spotify-server")

def get_config() -> Dict[str, str]:
    """Helper to get configuration from environment or settings.json."""
    config = {
        "client_id": os.environ.get("SPOTIPY_CLIENT_ID", ""),
        "client_secret": os.environ.get("SPOTIPY_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
    }

    # Try loading from settings.json if environment variables are missing
    settings_path = Path(__file__).parent / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                if not config["client_id"]: config["client_id"] = settings.get("SPOTIPY_CLIENT_ID", "")
                if not config["client_secret"]: config["client_secret"] = settings.get("SPOTIPY_CLIENT_SECRET", "")
                if "SPOTIPY_REDIRECT_URI" in settings: config["redirect_uri"] = settings["SPOTIPY_REDIRECT_URI"]
        except Exception:
            pass
    return config

def get_spotify_client():
    if spotipy is None:
        return None
    
    config = get_config()
    if not config["client_id"] or not config["client_secret"]:
        return None

    scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-modify-public playlist-modify-private"
    
    # Use a custom cache path to avoid permission issues in some environments
    cache_path = Path(__file__).parent / ".spotify_cache"
    
    auth_manager = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scope=scope,
        cache_path=str(cache_path),
        open_browser=True # Attempt to open browser automatically on desktop systems
    )
    
    return spotipy.Spotify(auth_manager=auth_manager)

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available Spotify tools."""
    return [
        Tool(
            name="spotify_get_current_track",
            description="Get information about the track currently playing on Spotify.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="spotify_search",
            description="Search for tracks, artists, albums, or playlists on Spotify.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "type": {"type": "string", "description": "Type: track, artist, album, or playlist", "default": "track"}
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="spotify_play",
            description="Play a track, album, or playlist by URI, or resume playback.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uri": {"type": "string", "description": "Spotify URI (e.g. spotify:track:...) to play. Leave empty to resume."},
                },
            },
        ),
        Tool(
            name="spotify_pause",
            description="Pause Spotify playback.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="spotify_next",
            description="Skip to the next track on Spotify.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="spotify_previous",
            description="Skip to the previous track on Spotify.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="spotify_set_volume",
            description="Set the volume for Spotify playback.",
            inputSchema={
                "type": "object",
                "properties": {
                    "volume_percent": {"type": "integer", "description": "Volume percentage (0-100)"},
                },
                "required": ["volume_percent"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> CallToolResult:
    """Handle Spotify tool calls."""
    if spotipy is None:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'spotipy' library not installed. Please run pip install spotipy.")],
            isError=True
        )

    sp = get_spotify_client()
    if sp is None:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Spotify credentials missing. Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.")],
            isError=True
        )

    try:
        if name == "spotify_get_current_track":
            current = sp.current_playback()
            if not current or not current.get("item"):
                return CallToolResult(content=[TextContent(type="text", text="No track currently playing.")])
            
            track = current["item"]
            artist = ", ".join([a["name"] for a in track["artists"]])
            output = f"Playing: {track['name']} by {artist}\nAlbum: {track['album']['name']}\nProgress: {current['progress_ms'] // 1000}s / {track['duration_ms'] // 1000}s"
            return CallToolResult(content=[TextContent(type="text", text=output)])

        elif name == "spotify_search":
            query = arguments["query"]
            stype = arguments.get("type", "track")
            results = sp.search(q=query, type=stype, limit=5)
            
            output = f"Search results for '{query}' ({stype}):\n"
            if stype == "track":
                for item in results['tracks']['items']:
                    artists = ", ".join([a['name'] for a in item['artists']])
                    output += f"- {item['name']} by {artists} (URI: {item['uri']})\n"
            elif stype == "artist":
                for item in results['artists']['items']:
                    output += f"- {item['name']} (URI: {item['uri']})\n"
            # ... other types can be added
            
            return CallToolResult(content=[TextContent(type="text", text=output)])

        elif name == "spotify_play":
            uri = arguments.get("uri")
            if uri:
                sp.start_playback(uris=[uri] if "track" in uri else None, context_uri=uri if "track" not in uri else None)
                return CallToolResult(content=[TextContent(type="text", text=f"Started playing: {uri}")])
            else:
                sp.start_playback()
                return CallToolResult(content=[TextContent(type="text", text="Playback resumed.")])

        elif name == "spotify_pause":
            sp.pause_playback()
            return CallToolResult(content=[TextContent(type="text", text="Playback paused.")])

        elif name == "spotify_next":
            sp.next_track()
            return CallToolResult(content=[TextContent(type="text", text="Skipped to next track.")])

        elif name == "spotify_previous":
            sp.previous_track()
            return CallToolResult(content=[TextContent(type="text", text="Skipped to previous track.")])

        elif name == "spotify_set_volume":
            volume = arguments["volume_percent"]
            sp.volume(volume)
            return CallToolResult(content=[TextContent(type="text", text=f"Volume set to {volume}%.")])

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        # Check for authentication URL requirement
        if "re-authenticate" in str(e) or "http" in str(e):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Authentication required. Please check terminal for OAuth flow or ensure credentials are correct. Error: {str(e)}")],
                isError=True
            )
        return CallToolResult(
            content=[TextContent(type="text", text=f"Spotify Error: {str(e)}")],
            isError=True
        )

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="spotify-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import os
    import sys
    # Recursive cleaner: if we detecting we are in a "dirty" environment that prints 
    # things on startup (like "Welcome back"), we re-run ourselves and filter stdout.
    if os.environ.get("MCP_CLEANER_OK") != "TRUE":
        import subprocess
        new_env = os.environ.copy()
        new_env["MCP_CLEANER_OK"] = "TRUE"
        proc = subprocess.Popen(
            [sys.executable] + sys.argv, 
            stdout=subprocess.PIPE, 
            stdin=sys.stdin, 
            stderr=sys.stderr, 
            env=new_env
        )
        
        # Filter EVERY line of stdout to ensure only valid JSON-RPC reaches the client
        for line in proc.stdout:
            stripped = line.strip()
            if stripped.startswith(b'{'):
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            elif stripped:
                # Redirect noise to stderr for debugging
                sys.stderr.buffer.write(b"[DEBUG] Discarded noise: " + line)
                sys.stderr.flush()
        
        sys.exit(proc.wait())
    else:
        # We are the "clean" child process
        asyncio.run(main())
