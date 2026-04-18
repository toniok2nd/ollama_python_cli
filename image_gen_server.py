from mcp.server.fastmcp import FastMCP
import asyncio
import urllib.parse
from typing import Optional

# Check for httpx
try:
    import httpx
except ImportError:
    httpx = None

# Initialize FastMCP Server with a custom result formatter that does not add extra newlines.
# The default FastMCP formatter wraps the tool output in a JSON‑style block which often results in a leading/trailing newline.
# By providing our own formatter we can forward the raw string exactly as the tool returns it.

def plain_formatter(tool_name: str, output: str) -> str:
    """Return the tool output unchanged.
    FastMCP will still send it over the transport, but it will not inject extra line breaks or markdown.
    """
    return output

mcp = FastMCP("image-gen-server", result_formatter=plain_formatter)

@mcp.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int = 42,
    filename: Optional[str] = None,
) -> str:
    """Generate an image from a text prompt using Pollinations AI.

    Args:
        prompt: Text description of the image to generate.
        width: Image width (default 1024).
        height: Image height (default 1024).
        seed: Random seed for reproducibility (default 42).
        filename: Optional filename to save the image (e.g., 'cat.png').
                  If provided, the image will be written to the current directory.

    Returns:
        If *filename* is supplied, a confirmation string is returned.
        Otherwise the direct URL of the generated image is returned **without any surrounding text**
        so that callers can embed it inline without extra line breaks.
    """
    if httpx is None:
        return "Error: 'httpx' library not installed. Please install the 'Medium' or 'Full' tier."

    encoded_prompt = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?"
        f"width={width}&height={height}&seed={seed}&nologo=true"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            if response.status_code != 200:
                return f"Error: Failed to generate image. Status code: {response.status_code}"

            image_data = response.content

            if filename:
                # Save the image to disk and return a friendly message.
                with open(filename, "wb") as f:
                    f.write(image_data)
                return f"Image saved to {filename}"
            else:
                # Return the direct URL only – callers can embed it inline.
                return url
    except Exception as e:
        return f"Error connecting to image generation service: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
