import sys
import asyncio
import json
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

# Optional dependencies handled gracefully
try:
    from youtubesearchpython import VideosSearch, Video
except ImportError:
    VideosSearch = None
    Video = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

server = Server("youtube-mcp-server")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available YouTube tools."""
    return [
        Tool(
            name="search_youtube",
            description="Search for YouTube videos by query. Returns titles, links, and snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_youtube_transcript",
            description="Get the transcript/subtitles for a YouTube video URL or ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "video_id_or_url": {"type": "string", "description": "YouTube video URL or Video ID"},
                },
                "required": ["video_id_or_url"],
            },
        ),
        Tool(
            name="get_youtube_info",
            description="Get detailed metadata for a YouTube video (title, views, description).",
            inputSchema={
                "type": "object",
                "properties": {
                    "video_id_or_url": {"type": "string", "description": "YouTube video URL or Video ID"},
                },
                "required": ["video_id_or_url"],
            },
        ),
    ]

def extract_video_id(url_or_id: str) -> str:
    """Helper to extract video ID from various URL formats."""
    import re
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # Simple regex for common YT URL formats
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'be\/([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> CallToolResult:
    """Handle YouTube tool calls."""
    if not arguments:
        return CallToolResult(content=[TextContent(type="text", text="Error: Missing arguments")], isError=True)

    if name == "search_youtube":
        if not VideosSearch:
            return CallToolResult(content=[TextContent(type="text", text="Error: youtube-search-python not installed")], isError=True)
        
        query = arguments.get("query")
        limit = arguments.get("limit", 5)
        try:
            search = VideosSearch(query, limit=limit)
            result = search.result()
            
            output = []
            for v in result.get('result', []):
                output.append(f"Title: {v['title']}\nURL: {v['link']}\nDuration: {v['duration']}\nDescription: {v.get('accessibility', {}).get('title', 'N/A')}\n---")
            
            return CallToolResult(content=[TextContent(type="text", text="\n".join(output) if output else "No results found.")])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error performing search: {str(e)}")], isError=True)

    elif name == "get_youtube_transcript":
        if not YouTubeTranscriptApi:
            return CallToolResult(content=[TextContent(type="text", text="Error: youtube-transcript-api not installed")], isError=True)
        
        video_id = extract_video_id(arguments.get("video_id_or_url"))
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([t['text'] for t in transcript_list])
            return CallToolResult(content=[TextContent(type="text", text=full_text)])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error fetching transcript: {str(e)}")], isError=True)

    elif name == "get_youtube_info":
        if not Video:
            return CallToolResult(content=[TextContent(type="text", text="Error: youtube-search-python not installed")], isError=True)
        
        video_id = extract_video_id(arguments.get("video_id_or_url"))
        try:
            v_info = Video.getInfo(f"https://www.youtube.com/watch?v={video_id}")
            info_text = (
                f"Title: {v_info.get('title')}\n"
                f"Author: {v_info.get('author', {}).get('name')}\n"
                f"Views: {v_info.get('viewCount', {}).get('text')}\n"
                f"Date: {v_info.get('publishDate')}\n"
                f"Description: {v_info.get('description')[:500]}..."
            )
            return CallToolResult(content=[TextContent(type="text", text=info_text)])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error getting info: {str(e)}")], isError=True)

    return CallToolResult(content=[TextContent(type="text", text=f"Unknown tool: {name}")], isError=True)

if __name__ == "__main__":
    # Defensive: redirect any accidental library prints to stderr
    # so they don't pollute the MCP stdout channel.
    import sys
    orig_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="youtube-mcp-server",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    
    try:
        asyncio.run(run())
    finally:
        sys.stdout = orig_stdout
