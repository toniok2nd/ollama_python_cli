from mcp.server.fastmcp import FastMCP
import asyncio
import urllib.parse
from typing import Optional

# Check for httpx
try:
    import httpx
except ImportError:
    httpx = None

# Initialize FastMCP Server
mcp = FastMCP("image-gen-server")

@mcp.tool()
async def generate_image(prompt: str, width: int = 1024, height: int = 1024, seed: int = 42, filename: Optional[str] = None) -> str:
    """
    Generate an image from a text prompt using Pollinations AI. No API key required.
    
    Args:
        prompt: Text description of the image to generate.
        width: Image width (default 1024).
        height: Image height (default 1024).
        seed: Random seed for reproducibility (default 42).
        filename: Optional filename to save the image (e.g., 'cat.png'). If provided, image will be saved to the current directory.
    """
    if httpx is None:
        return "Error: 'httpx' library not installed. Please install the 'Medium' or 'Full' tier."

    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            if response.status_code != 200:
                return f"Error: Failed to generate image. Status code: {response.status_code}"
            
            image_data = response.content
            
            if filename:
                with open(filename, "wb") as f:
                    f.write(image_data)
                return f"Image generated and saved to {filename}"
            else:
                return f"Image generated successfully at {url}"
                
    except Exception as e:
        return f"Error connecting to image generation service: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
