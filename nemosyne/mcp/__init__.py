from mcp.server.fastmcp import FastMCP

"""MCP tools exposed by Nemosyne."""
mcp = FastMCP(
    "Nemosyne",
    instructions="Store completed AI agent sessions for later skill curation.",
    host="127.0.0.1",
    port=8000,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)
