import asyncio
import base64
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

# Check for httpx
try:
    import httpx
except ImportError:
    httpx = None

from mcp.server.stdio import stdio_server
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    CallToolResult,
)

# Initialize MCP Server
server = Server("image-gen-server")

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available image generation tools."""
    return [
        Tool(
            name="generate_image",
            description="Generate an image from a text prompt using Pollinations AI. No API key required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string", 
                        "description": "Text description of the image to generate"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Image width (default 1024)",
                        "default": 1024
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height (default 1024)",
                        "default": 1024
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility",
                        "default": 42
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename to save the image (e.g. 'cat.png'). If provided, image will be saved to the current directory."
                    }
                },
                "required": ["prompt"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> CallToolResult:
    """Handle image generation tool calls."""
    if name != "generate_image":
        raise ValueError(f"Unknown tool: {name}")

    if httpx is None:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'httpx' library not installed. Please install the 'Medium' or 'Full' tier.")],
            isError=True
        )

    if not arguments:
        raise ValueError("Missing arguments")

    prompt = arguments["prompt"]
    width = arguments.get("width", 1024)
    height = arguments.get("height", 1024)
    seed = arguments.get("seed", 42)
    filename = arguments.get("filename")

    # Construct Pollinations AI URL
    import urllib.parse
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            image_data = response.content

        results = []
        
        # 1. Optionally save to file
        save_msg = ""
        if filename:
            # Ensure safe filename
            safe_filename = "".join([c for c in filename if c.isalnum() or c in "._-"]).strip()
            if not safe_filename:
                safe_filename = f"gen_{uuid.uuid4().hex[:8]}.png"
            
            with open(safe_filename, 'wb') as f:
                f.write(image_data)
            save_msg = f"\nImage saved to: {safe_filename}"
            results.append(TextContent(type="text", text=f"Success! {save_msg}"))

        # 2. Return as ImageContent
        base64_image = base64.b64encode(image_data).decode("utf-8")
        results.append(ImageContent(
            type="image",
            data=base64_image,
            mimeType="image/png"
        ))

        return CallToolResult(content=results)

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error generating image: {str(e)}")],
            isError=True
        )

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="image-gen-server",
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
        # We use sys.executable to run the same interpreter, bypassing shell greetings if possible
        # through the pipe filtering.
        proc = subprocess.Popen(
            [sys.executable] + sys.argv, 
            stdout=subprocess.PIPE, 
            stdin=sys.stdin, 
            stderr=sys.stderr, 
            env=new_env
        )
        
        # Filter stdout until we see valid JSON
        found_json = False
        for line in proc.stdout:
            if not found_json and line.strip().startswith(b'{'):
                found_json = True
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            elif found_json:
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            else:
                # Discard noise to stderr for debugging
                sys.stderr.buffer.write(b"[DEBUG] Discarded noise: " + line)
                sys.stderr.flush()
        
        # Continue piping if needed (though the loop above handles most)
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk: break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        
        sys.exit(proc.wait())
    else:
        # We are the "clean" child process
        asyncio.run(main())
