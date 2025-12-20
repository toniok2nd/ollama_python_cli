import asyncio
import os
import json
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

# Check for tuya-iot-python-sdk
try:
    from tuya_iot import TuyaOpenAPI, AuthType
except ImportError:
    TuyaOpenAPI = None

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
server = Server("konyks-server")

def get_config() -> Dict[str, str]:
    """Helper to get configuration from environment or settings.json."""
    config = {
        "client_id": os.environ.get("TUYA_CLIENT_ID", ""),
        "client_secret": os.environ.get("TUYA_CLIENT_SECRET", ""),
        "base_url": os.environ.get("TUYA_BASE_URL", "https://openapi.tuyaeu.com"),
        "uid": os.environ.get("TUYA_UID", ""),
    }

    # Try loading from settings.json if environment variables are missing
    settings_path = Path(__file__).parent / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                if not config["client_id"]: config["client_id"] = settings.get("TUYA_CLIENT_ID", "")
                if not config["client_secret"]: config["client_secret"] = settings.get("TUYA_CLIENT_SECRET", "")
                if not config["uid"]: config["uid"] = settings.get("TUYA_UID", "")
                # base_url usually defaults correctly but can be overridden
                if "TUYA_BASE_URL" in settings: config["base_url"] = settings["TUYA_BASE_URL"]
        except Exception:
            pass
    return config

def get_tuya_api():
    if TuyaOpenAPI is None:
        return None
    
    config = get_config()
    if not config["client_id"] or not config["client_secret"]:
        return None

    openapi = TuyaOpenAPI(config["base_url"], config["client_id"], config["client_secret"], AuthType.CUSTOM)
    openapi.connect()
    return openapi

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available Konyks/Tuya tools."""
    return [
        Tool(
            name="konyks_get_devices",
            description="List all Konyks/Tuya devices and their current status.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="konyks_switch_device",
            description="Turn a Konyks/Tuya device on or off.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The unique ID of the device."
                    },
                    "switch_state": {
                        "type": "boolean",
                        "description": "True to turn on, False to turn off."
                    }
                },
                "required": ["device_id", "switch_state"],
            },
        ),
        Tool(
            name="konyks_set_value",
            description="Set a specific property value for a Konyks/Tuya device (e.g., brightness, color).",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The unique ID of the device."
                    },
                    "code": {
                        "type": "string",
                        "description": "The function code (e.g., 'bright_value', 'temp_value')."
                    },
                    "value": {
                        "type": "integer",
                        "description": "The value to set."
                    }
                },
                "required": ["device_id", "code", "value"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> CallToolResult:
    """Handle Konyks/Tuya tool calls."""
    if TuyaOpenAPI is None:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'tuya-iot-py-sdk' not installed. Please run pip install tuya-iot-py-sdk.")],
            isError=True
        )

    openapi = get_tuya_api()
    if openapi is None:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Tuya API credentials missing or invalid. Set TUYA_CLIENT_ID and TUYA_CLIENT_SECRET.")],
            isError=True
        )

    config = get_config()
    uid = config["uid"]

    try:
        if name == "konyks_get_devices":
            if not uid:
                return CallToolResult(content=[TextContent(type="text", text="Error: TUYA_UID is required for listing devices.")], isError=True)
            
            # Get device list for user
            response = openapi.get(f"/v1.0/users/{uid}/devices")
            if not response.get("success"):
                return CallToolResult(content=[TextContent(type="text", text=f"API Error: {response.get('msg')}")], isError=True)
            
            devices = response.get("result", [])
            output = "Konyks/Tuya Devices:\n"
            for dev in devices:
                output += f"- {dev.get('name')} (ID: {dev.get('id')}) | Online: {dev.get('online')}\n"
                status = dev.get("status", [])
                for s in status:
                    output += f"  - {s.get('code')}: {s.get('value')}\n"
            
            return CallToolResult(content=[TextContent(type="text", text=output)])

        elif name == "konyks_switch_device":
            device_id = arguments["device_id"]
            state = arguments["switch_state"]
            
            commands = {'commands': [{'code': 'switch_1', 'value': state}]} # assuming switch_1 as default, might need adjustment
            # Some devices use 'switch' or 'switch_led' etc. 
            # We could try to query device functions first but let's try common 'switch_1'
            
            response = openapi.post(f"/v1.0/devices/{device_id}/commands", commands)
            if not response.get("success") and "switch_1" in str(response):
                # Retry with common code 'switch'
                commands = {'commands': [{'code': 'switch', 'value': state}]}
                response = openapi.post(f"/v1.0/devices/{device_id}/commands", commands)

            if response.get("success"):
                return CallToolResult(content=[TextContent(type="text", text=f"Success: Device {device_id} turned {'on' if state else 'off'}.")])
            else:
                return CallToolResult(content=[TextContent(type="text", text=f"API Error: {response.get('msg')}")], isError=True)

        elif name == "konyks_set_value":
            device_id = arguments["device_id"]
            code = arguments["code"]
            value = arguments["value"]
            
            commands = {'commands': [{'code': code, 'value': value}]}
            response = openapi.post(f"/v1.0/devices/{device_id}/commands", commands)
            
            if response.get("success"):
                return CallToolResult(content=[TextContent(type="text", text=f"Success: Set {code} to {value} for device {device_id}. ")])
            else:
                return CallToolResult(content=[TextContent(type="text", text=f"API Error: {response.get('msg')}")], isError=True)

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            isError=True
        )

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="konyks-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import os
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
