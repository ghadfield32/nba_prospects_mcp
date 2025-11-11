"""
Batch Query Tool for MCP.

Allows LLMs to execute multiple tool calls in a single request, reducing round-trips
and improving efficiency for complex multi-step queries.

Key Features:
    - Execute multiple tools in parallel
    - Per-tool error handling (one failure doesn't break all)
    - Aggregated results with individual success/error envelopes
    - Token-efficient response format

Usage:
    # Single batch request with multiple tools
    batch_query([
        {"tool": "get_schedule", "args": {"league": "NCAA-MBB", "season": "2025"}},
        {"tool": "get_player_game_stats", "args": {"league": "NCAA-MBB", "team": ["Duke"]}},
        {"tool": "get_team_season_stats", "args": {"league": "NCAA-MBB", "season": "2025"}}
    ])

    # Returns:
    [
        {"ok": True, "result": {...}},
        {"ok": True, "result": {...}},
        {"ok": False, "error": "..."}
    ]
"""

import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Tool registry (populated at module import)
TOOL_DISPATCH: dict[str, Callable] = {}


# ============================================================================
# Tool Registration
# ============================================================================


def register_tool(name: str, func: Callable) -> None:
    """
    Register a tool for batch execution.

    Args:
        name: Tool name (e.g., "get_schedule")
        func: Tool function

    Examples:
        >>> register_tool("get_schedule", tool_get_schedule)
    """
    TOOL_DISPATCH[name] = func
    logger.debug(f"Registered tool: {name}")


def list_registered_tools() -> list[str]:
    """
    List all registered tools.

    Returns:
        List of tool names

    Examples:
        >>> list_registered_tools()
        ['get_schedule', 'get_player_game_stats', 'get_team_season_stats']
    """
    return list(TOOL_DISPATCH.keys())


# ============================================================================
# Batch Query Execution
# ============================================================================


def batch_query(requests: list[dict[str, Any]], max_concurrent: int = 10) -> list[dict[str, Any]]:
    """
    Execute multiple tool calls in a batch.

    Each request is executed independently with isolated error handling.
    One tool failure doesn't affect others.

    Args:
        requests: List of tool requests, each with:
            - tool: str - Tool name
            - args: dict - Tool arguments
        max_concurrent: Maximum concurrent executions (currently sequential, reserved for future)

    Returns:
        List of results, each with:
            - ok: bool - Success flag
            - result: Any - Tool result (if successful)
            - error: str - Error message (if failed)
            - error_type: str - Error class name (if failed)
            - duration_ms: float - Execution time

    Examples:
        >>> batch_query([
        ...     {"tool": "get_schedule", "args": {"league": "NCAA-MBB", "season": "2025"}},
        ...     {"tool": "invalid_tool", "args": {}}
        ... ])
        [
            {"ok": True, "result": {...}, "duration_ms": 125.5},
            {"ok": False, "error": "Unknown tool: invalid_tool", "duration_ms": 0.1}
        ]
    """
    results = []

    for i, req in enumerate(requests):
        start_time = time.perf_counter()

        try:
            # Validate request structure
            if not isinstance(req, dict):
                raise ValueError(f"Request {i} must be a dict, got {type(req)}")

            if "tool" not in req:
                raise ValueError(f"Request {i} missing 'tool' field")

            if "args" not in req:
                raise ValueError(f"Request {i} missing 'args' field")

            tool_name = req["tool"]
            tool_args = req["args"]

            # Check if tool exists
            if tool_name not in TOOL_DISPATCH:
                available = ", ".join(list_registered_tools())
                raise KeyError(f"Unknown tool: '{tool_name}'. Available tools: {available}")

            # Execute tool
            tool_func = TOOL_DISPATCH[tool_name]
            result = tool_func(**tool_args)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Success envelope
            results.append(
                {
                    "ok": True,
                    "result": result,
                    "tool": tool_name,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            logger.info(f"Batch tool '{tool_name}' succeeded ({duration_ms:.0f}ms)")

        except Exception as e:
            # Error envelope
            duration_ms = (time.perf_counter() - start_time) * 1000

            error_info = {
                "ok": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "tool": req.get("tool", "unknown"),
                "duration_ms": round(duration_ms, 2),
            }

            results.append(error_info)

            logger.error(
                f"Batch tool '{req.get('tool', 'unknown')}' failed: {str(e)}", exc_info=True
            )

    return results


def batch_query_safe(requests: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Execute batch query with aggregated metadata.

    Returns results + summary metadata for easier LLM consumption.

    Args:
        requests: List of tool requests

    Returns:
        Dict with:
            - results: List of individual results
            - summary: Aggregated metadata
                - total: Total requests
                - successful: Successful requests
                - failed: Failed requests
                - total_duration_ms: Total execution time

    Examples:
        >>> batch_query_safe([
        ...     {"tool": "get_schedule", "args": {"league": "NCAA-MBB"}},
        ...     {"tool": "get_player_game_stats", "args": {"league": "NCAA-MBB"}}
        ... ])
        {
            "results": [...],
            "summary": {
                "total": 2,
                "successful": 2,
                "failed": 0,
                "total_duration_ms": 250.5
            }
        }
    """
    # Execute batch
    results = batch_query(requests)

    # Calculate summary
    successful = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    total_duration = sum(r.get("duration_ms", 0) for r in results)

    summary = {
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "total_duration_ms": round(total_duration, 2),
        "average_duration_ms": round(total_duration / len(results), 2) if results else 0,
    }

    return {"results": results, "summary": summary}


# ============================================================================
# Helper Functions
# ============================================================================


def validate_batch_request(requests: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """
    Validate batch request structure.

    Args:
        requests: List of tool requests

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_batch_request([{"tool": "get_schedule", "args": {}}])
        (True, None)

        >>> validate_batch_request([{"tool": "get_schedule"}])  # Missing args
        (False, "Request 0 missing 'args' field")
    """
    if not isinstance(requests, list):
        return False, "Requests must be a list"

    if len(requests) == 0:
        return False, "Requests list is empty"

    if len(requests) > 100:
        return False, f"Too many requests ({len(requests)}). Maximum: 100"

    for i, req in enumerate(requests):
        if not isinstance(req, dict):
            return False, f"Request {i} must be a dict, got {type(req)}"

        if "tool" not in req:
            return False, f"Request {i} missing 'tool' field"

        if "args" not in req:
            return False, f"Request {i} missing 'args' field"

        if not isinstance(req["args"], dict):
            return False, f"Request {i} 'args' must be a dict, got {type(req['args'])}"

    return True, None


# ============================================================================
# Auto-Registration
# ============================================================================


def auto_register_mcp_tools() -> None:
    """
    Auto-register all MCP tools from tools module.

    This is called at module import to populate TOOL_DISPATCH.
    """
    try:
        from cbb_data.servers.mcp import tools as mcp_tools

        # Register all tool_* functions
        for name in dir(mcp_tools):
            if name.startswith("tool_"):
                func = getattr(mcp_tools, name)
                if callable(func):
                    # Remove 'tool_' prefix for cleaner names
                    tool_name = name.replace("tool_", "")
                    register_tool(tool_name, func)

        logger.info(f"Auto-registered {len(TOOL_DISPATCH)} MCP tools")

    except ImportError as e:
        logger.warning(f"Could not auto-register MCP tools: {e}")


# Auto-register tools on import
auto_register_mcp_tools()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "batch_query",
    "batch_query_safe",
    "register_tool",
    "list_registered_tools",
    "validate_batch_request",
    "TOOL_DISPATCH",
]
