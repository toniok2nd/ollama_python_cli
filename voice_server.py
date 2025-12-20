import asyncio
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
# edge_tts will be imported locally in handle_call_tool
from mcp.server.stdio import stdio_server
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

# Initialize MCP Server
server = Server("voice-server")

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available voice tools."""
    return [
        Tool(
            name="speak",
            description="Convert text to speech and play it on the system speakers using Microsoft Edge TTS.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to speak"
                    },
                    "voice": {
                        "type": "string",
                        "description": "Optional voice name (e.g., 'en-US-AvaNeural', 'en-GB-SoniaNeural'). Default is a clear US English voice.",
                        "default": "en-US-AvaNeural"
                    },
                    "rate": {
                        "type": "string",
                        "description": "Speed of speech (e.g., '+0%', '-10%')",
                        "default": "+0%"
                    }
                },
                "required": ["text"],
            },
        )
    ]

async def play_audio(file_path: str):
    """Play audio using a system player."""
    # Try common CLI players
    players = ["mpv", "ffplay", "vlc", "aplay"]
    for player in players:
        if shutil.which(player):
            if player == "ffplay":
                # -nodisp -autoexit avoids opening a window
                cmd = ["ffplay", "-nodisp", "-autoexit", file_path]
            elif player == "vlc":
                cmd = ["cvlc", "--play-and-exit", file_path]
            else:
                cmd = [player, file_path]
            
            try:
                # Run in background to not block the server if needed? 
                # Actually, for TTS, sequential might be better or handled by the caller.
                subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                return True
            except Exception:
                continue
    return False

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> CallToolResult:
    """Handle voice tool calls."""
    if name != "speak":
        raise ValueError(f"Unknown tool: {name}")

    try:
        import edge_tts as _edge_tts
    except ImportError:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'edge-tts' library not installed. Please install the 'Medium' or 'Full' tier.")],
            isError=True
        )

    text = arguments["text"]
    voice = arguments.get("voice", "en-US-AvaNeural")
    rate = arguments.get("rate", "+0%")

    try:
        # Generate speech to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        communicate = _edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(tmp_path)

        # Play the audio
        played = await play_audio(tmp_path)
        
        # Cleanup
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        if played:
            return CallToolResult(content=[TextContent(type="text", text=f"Success! Spoke: '{text[:50]}...'" )])
        else:
            return CallToolResult(
                content=[TextContent(type="text", text="Speech generated but no audio player found (mpv, ffplay, vlc).")],
                isError=True
            )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error in voice synthesis: {str(e)}")],
            isError=True
        )

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="voice-server",
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
