from mcp.server.fastmcp import FastMCP
import os
import json
from typing import Dict, Optional, Any
from pathlib import Path

# Check for tuya-iot-python-sdk
try:
    from tuya_iot import TuyaOpenAPI, AuthType
except ImportError:
    TuyaOpenAPI = None

# Initialize FastMCP Server
mcp = FastMCP("konyks-server")

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

@mcp.tool()
def konyks_get_devices() -> str:
    """List all Konyks/Tuya devices and their current status."""
    if TuyaOpenAPI is None:
        return "Error: 'tuya-iot-py-sdk' not installed. Please run pip install tuya-iot-py-sdk."

    openapi = get_tuya_api()
    if openapi is None:
        return "Error: Tuya API credentials missing or invalid. Set TUYA_CLIENT_ID and TUYA_CLIENT_SECRET."

    config = get_config()
    uid = config["uid"]
    if not uid:
        return "Error: TUYA_UID is required for listing devices."
    
    response = openapi.get(f"/v1.0/users/{uid}/devices")
    if not response.get("success"):
        return f"API Error: {response.get('msg')}"
    
    devices = response.get("result", [])
    output = "Konyks/Tuya Devices:\n"
    for dev in devices:
        output += f"- {dev.get('name')} (ID: {dev.get('id')}) | Online: {dev.get('online')}\n"
        status = dev.get("status", [])
        for s in status:
            output += f"  - {s.get('code')}: {s.get('value')}\n"
    
    return output

@mcp.tool()
def konyks_switch_device(device_id: str, switch_state: bool) -> str:
    """
    Turn a Konyks/Tuya device on or off.
    
    Args:
        device_id: The unique ID of the device.
        switch_state: True to turn on, False to turn off.
    """
    if TuyaOpenAPI is None:
        return "Error: 'tuya-iot-py-sdk' not installed."

    openapi = get_tuya_api()
    if openapi is None:
        return "Error: Tuya API credentials missing."

    commands = {'commands': [{'code': 'switch_1', 'value': switch_state}]}
    
    response = openapi.post(f"/v1.0/devices/{device_id}/commands", commands)
    if not response.get("success") and "switch_1" in str(response):
        # Retry with common code 'switch'
        commands = {'commands': [{'code': 'switch', 'value': switch_state}]}
        response = openapi.post(f"/v1.0/devices/{device_id}/commands", commands)

    if response.get("success"):
        return f"Success: Device {device_id} turned {'on' if switch_state else 'off'}."
    else:
        return f"API Error: {response.get('msg')}"

@mcp.tool()
def konyks_set_value(device_id: str, code: str, value: int) -> str:
    """
    Set a specific property value for a Konyks/Tuya device (e.g., brightness, color).
    
    Args:
        device_id: The unique ID of the device.
        code: The function code (e.g., 'bright_value', 'temp_value').
        value: The value to set.
    """
    if TuyaOpenAPI is None:
        return "Error: 'tuya-iot-py-sdk' not installed."

    openapi = get_tuya_api()
    if openapi is None:
        return "Error: Tuya API credentials missing."
    
    commands = {'commands': [{'code': code, 'value': value}]}
    response = openapi.post(f"/v1.0/devices/{device_id}/commands", commands)
    
    if response.get("success"):
        return f"Success: Set {code} to {value} for device {device_id}."
    else:
        return f"API Error: {response.get('msg')}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
