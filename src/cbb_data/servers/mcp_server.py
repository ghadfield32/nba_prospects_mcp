"""
MCP (Model Context Protocol) Server for college basketball data.

Provides LLM-friendly tools for accessing basketball data via the MCP protocol.

Usage:
    # Start server in stdio mode (for Claude Desktop)
    python -m cbb_data.servers.mcp_server

    # Start server in SSE mode (for web clients)
    python -m cbb_data.servers.mcp_server --transport sse --port 3000
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, Resource, Prompt, TextContent
except ImportError:
    print("ERROR: mcp library is not installed. Install it with:")
    print("  pip install mcp")
    print("  or: uv pip install mcp")
    print("\nFor now, creating a simplified JSON-RPC server...")
    Server = None
    stdio_server = None

from .mcp.tools import TOOLS
from .mcp.resources import RESOURCES, STATIC_RESOURCES, resource_get_dataset_info, resource_get_league_info
from .mcp.prompts import PROMPTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MCP Server Implementation
# ============================================================================

class BasketballDataMCPServer:
    """
    MCP Server for college basketball data.

    Provides 10 tools, 3 resource types, and 10 prompt templates for
    LLM access to basketball data.
    """

    def __init__(self, name: str = "cbb-data"):
        """
        Initialize MCP server.

        Args:
            name: Server name for MCP registration
        """
        self.name = name
        self.server = None
        self.tools_registry = {tool["name"]: tool for tool in TOOLS}

        logger.info(f"Initialized {name} MCP server")
        logger.info(f"Registered {len(TOOLS)} tools")
        logger.info(f"Registered {len(STATIC_RESOURCES)} resources")
        logger.info(f"Registered {len(PROMPTS)} prompts")

    def setup_server(self) -> Optional[Server]:
        """
        Set up the MCP server with tools, resources, and prompts.

        Returns:
            Configured MCP Server instance, or None if MCP not available
        """
        if Server is None:
            logger.warning("MCP library not available, using fallback mode")
            return None

        # Create server
        self.server = Server(self.name)

        # Register list_tools handler
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"]
                )
                for tool in TOOLS
            ]

        # Register call_tool handler
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Call a tool with arguments."""
            logger.info(f"Tool called: {name} with args: {arguments}")

            # Find tool
            tool = self.tools_registry.get(name)
            if not tool:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Tool '{name}' not found"
                    })
                )]

            # Execute tool handler
            try:
                result = tool["handler"](**arguments)
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })
                )]

        # Register list_resources handler
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List all available resources."""
            return [
                Resource(
                    uri=res["uri"],
                    name=res["name"],
                    description=res["description"],
                    mimeType=res["mimeType"]
                )
                for res in STATIC_RESOURCES
            ]

        # Register read_resource handler
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource by URI."""
            logger.info(f"Resource requested: {uri}")

            # Handle dataset info resources
            if uri.startswith("cbb://datasets/") and uri != "cbb://datasets/":
                dataset_id = uri.replace("cbb://datasets/", "")
                result = resource_get_dataset_info(dataset_id)
                return result["text"]

            # Handle league info resources
            if uri.startswith("cbb://leagues/"):
                league = uri.replace("cbb://leagues/", "")
                result = resource_get_league_info(league)
                return result["text"]

            return f"Resource not found: {uri}"

        # Register list_prompts handler
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            """List all available prompts."""
            return [
                Prompt(
                    name=prompt["name"],
                    description=prompt["description"],
                    arguments=prompt.get("arguments", [])
                )
                for prompt in PROMPTS
            ]

        # Register get_prompt handler
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Dict[str, Any]) -> str:
            """Get a prompt template with arguments filled in."""
            logger.info(f"Prompt requested: {name} with args: {arguments}")

            # Find prompt
            prompt = next((p for p in PROMPTS if p["name"] == name), None)
            if not prompt:
                return f"Prompt '{name}' not found"

            # Fill in template with arguments
            template = prompt["template"]

            # Handle special formatting for optional parameters
            if "season" in arguments:
                arguments["season_text"] = f" for the {arguments['season']} season"
                arguments["season_param"] = f"- season: {arguments['season']}"
            else:
                arguments["season_text"] = ""
                arguments["season_param"] = ""

            if "team" in arguments and "team_text" not in arguments:
                arguments["team_text"] = f" for {arguments['team']}"
                arguments["team_param"] = f"- team: [\"{arguments['team']}\"]"
            else:
                arguments["team_text"] = ""
                arguments["team_param"] = ""

            if "division" in arguments:
                arguments["division_text"] = f" {arguments['division']}"
                arguments["division_param"] = f"- division: \"{arguments['division']}\""
            else:
                arguments["division_text"] = ""
                arguments["division_param"] = ""

            if "players" in arguments:
                # Split comma-separated players into array format
                players_list = [p.strip() for p in arguments["players"].split(",")]
                arguments["players_array"] = json.dumps(players_list)

            # Set defaults
            if "limit" not in arguments:
                arguments["limit"] = 20
            if "days" not in arguments:
                arguments["days"] = 2

            return template.format(**arguments)

        logger.info("MCP server setup complete")
        return self.server

    async def run_stdio(self):
        """Run server in stdio mode (for Claude Desktop)."""
        if self.server is None:
            self.server = self.setup_server()

        if self.server is None or stdio_server is None:
            logger.error("MCP library not available, cannot start server")
            sys.exit(1)

        logger.info("Starting MCP server in stdio mode...")
        logger.info("Server ready for Claude Desktop connection")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

    async def run_sse(self, host: str = "localhost", port: int = 3000):
        """
        Run server in SSE mode (for web clients).

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        if self.server is None:
            self.server = self.setup_server()

        if self.server is None:
            logger.error("MCP library not available, cannot start server")
            sys.exit(1)

        logger.info(f"Starting MCP server in SSE mode on {host}:{port}...")
        logger.warning("SSE mode not yet implemented - use stdio mode")
        # TODO: Implement SSE transport
        sys.exit(1)


# ============================================================================
# CLI Entry Point
# ============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Start the College Basketball Data MCP server"
    )

    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio", "sse"],
        help="Transport mode: stdio (for Claude Desktop) or sse (for web clients)"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind to (SSE mode only)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port to bind to (SSE mode only)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
        help="Log level"
    )

    return parser.parse_args()


async def main():
    """Main entry point for MCP server."""
    args = parse_args()

    # Configure logging
    logging.getLogger().setLevel(args.log_level.upper())

    logger.info("=" * 70)
    logger.info("College Basketball Data MCP Server")
    logger.info("=" * 70)
    logger.info(f"Transport: {args.transport}")
    if args.transport == "sse":
        logger.info(f"Host: {args.host}")
        logger.info(f"Port: {args.port}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info("=" * 70)

    # Create and start server
    server = BasketballDataMCPServer("cbb-data")

    try:
        if args.transport == "stdio":
            await server.run_stdio()
        elif args.transport == "sse":
            await server.run_sse(args.host, args.port)
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 70)
        logger.info("Server stopped by user")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
