from mcp.server.fastmcp import FastMCP
import os

# Create an MCP server
mcp = FastMCP("Simple File System Server")

@mcp.tool()
def read_file(path: str) -> str:
    """Read the content of a file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {path}: {e}"

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file {path}: {e}"

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories in the given path."""
    try:
        return "\n".join(os.listdir(path))
    except Exception as e:
        return f"Error listing directory {path}: {e}"

@mcp.tool()
def create_directory(path: str) -> str:
    """Create a new directory."""
    try:
        os.makedirs(path, exist_ok=True)
        return f"Successfully created directory {path}"
    except Exception as e:
        return f"Error creating directory {path}: {e}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
        try:
            os.chdir(root_dir)
        except Exception as e:
            # We can't print to stdout as it's used for MCP transport
            # Log to stderr
            print(f"Error changing directory to {root_dir}: {e}", file=sys.stderr)
            sys.exit(1)
            
    mcp.run(transport='stdio')
