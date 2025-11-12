"""
JSON Structured Logging for CBB Data Servers.

Provides structured logging that outputs JSON for easy parsing by log aggregators
(Elasticsearch, Splunk, CloudWatch, etc.). Includes request tracking, performance
metrics, and error details.

Usage:
    from cbb_data.servers.logging import log_event, log_error, log_request

    # Log a simple event
    log_event(service="api", event="cache_hit", dataset="schedule", rows=150)

    # Log a request
    log_request(
        service="rest",
        endpoint="/datasets/player_game",
        method="POST",
        status_code=200,
        duration_ms=45.3,
        request_id="abc-123"
    )

    # Log an error
    log_error(
        service="mcp",
        error="ValueError: Invalid season format",
        tool="get_schedule",
        request_id="xyz-789"
    )
"""

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# JSON Logging Functions
# ============================================================================


def log_event(**kwargs: Any) -> None:
    """
    Log a structured event as JSON to stdout.

    Automatically adds timestamp and ensures consistent formatting.

    Args:
        **kwargs: Arbitrary key-value pairs to log. Common keys:
            - service: Service name ("rest", "mcp", "api")
            - event: Event type ("cache_hit", "tool_call", "dataset_fetch")
            - request_id: Request tracking ID
            - tool: Tool/endpoint name
            - dataset: Dataset ID
            - rows: Number of rows
            - ms: Duration in milliseconds
            - error: Error message
            - Any other contextual data

    Example:
        >>> log_event(service="rest", event="query", dataset="schedule", rows=50, ms=120)
        {"ts": 1699999999.123, "service": "rest", "event": "query", "dataset": "schedule", "rows": 50, "ms": 120}
    """
    # Add timestamp if not already present
    kwargs.setdefault("ts", time.time())

    # Add ISO timestamp for human readability
    if "ts" in kwargs:
        dt = datetime.fromtimestamp(kwargs["ts"], tz=UTC)
        kwargs["timestamp"] = dt.isoformat()

    try:
        # Write to stdout (captured by Docker, systemd, etc.)
        sys.stdout.write(json.dumps(kwargs) + "\n")
        sys.stdout.flush()
    except Exception as e:
        # Fallback to standard logging if JSON serialization fails
        logger.error(f"Failed to write JSON log: {e}. Data: {kwargs}")


def log_request(
    service: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    request_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Log an HTTP request with structured data.

    Args:
        service: Service name ("rest", "mcp")
        endpoint: API endpoint or tool name
        method: HTTP method ("GET", "POST", etc.) or "MCP" for MCP calls
        status_code: HTTP status code or 0 for MCP
        duration_ms: Request duration in milliseconds
        request_id: Optional request tracking ID
        **kwargs: Additional context (user_agent, ip, rows, cached, etc.)

    Example:
        >>> log_request(
        ...     service="rest",
        ...     endpoint="/datasets/player_game",
        ...     method="POST",
        ...     status_code=200,
        ...     duration_ms=45.3,
        ...     request_id="abc-123",
        ...     rows=50,
        ...     cached=True
        ... )
    """
    log_data = {
        "event": "request",
        "service": service,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }

    if request_id:
        log_data["request_id"] = request_id

    # Add any additional context
    log_data.update(kwargs)

    log_event(**log_data)


def log_error(
    service: str,
    error: str,
    error_type: str | None = None,
    request_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Log an error with structured data.

    Args:
        service: Service name ("rest", "mcp", "api")
        error: Error message
        error_type: Error class name (ValueError, KeyError, etc.)
        request_id: Optional request tracking ID
        **kwargs: Additional context (tool, dataset, endpoint, etc.)

    Example:
        >>> log_error(
        ...     service="mcp",
        ...     error="Invalid season format '2024-25'",
        ...     error_type="ValueError",
        ...     tool="get_schedule",
        ...     request_id="xyz-789"
        ... )
    """
    log_data = {
        "event": "error",
        "service": service,
        "error": error,
    }

    if error_type:
        log_data["error_type"] = error_type

    if request_id:
        log_data["request_id"] = request_id

    # Add any additional context
    log_data.update(kwargs)

    log_event(**log_data)


def log_cache(
    action: str,
    dataset: str,
    league: str,
    season: str,
    rows: int | None = None,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """
    Log cache operations (hit, miss, save).

    Args:
        action: Cache action ("hit", "miss", "save")
        dataset: Dataset ID
        league: League name
        season: Season identifier
        rows: Number of rows (for saves/hits)
        duration_ms: Operation duration
        **kwargs: Additional context

    Example:
        >>> log_cache(
        ...     action="hit",
        ...     dataset="schedule",
        ...     league="NCAA-MBB",
        ...     season="2025",
        ...     rows=150,
        ...     duration_ms=0.5
        ... )
    """
    log_data: dict[str, Any] = {
        "event": "cache",
        "action": action,
        "dataset": dataset,
        "league": league,
        "season": season,
    }

    if rows is not None:
        log_data["rows"] = rows

    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)

    # Add any additional context
    log_data.update(kwargs)

    log_event(**log_data)


def log_tool_call(
    tool: str,
    service: str = "mcp",
    duration_ms: float | None = None,
    rows: int | None = None,
    request_id: str | None = None,
    success: bool = True,
    **kwargs: Any,
) -> None:
    """
    Log MCP tool calls.

    Args:
        tool: Tool name
        service: Service name (default: "mcp")
        duration_ms: Tool execution time
        rows: Number of rows returned
        request_id: Request tracking ID
        success: Whether tool succeeded
        **kwargs: Additional context (league, season, dataset, etc.)

    Example:
        >>> log_tool_call(
        ...     tool="get_player_game_stats",
        ...     duration_ms=125.5,
        ...     rows=50,
        ...     request_id="mcp-456",
        ...     league="NCAA-MBB",
        ...     season="2025"
        ... )
    """
    log_data = {
        "event": "tool_call",
        "service": service,
        "tool": tool,
        "success": success,
    }

    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)

    if rows is not None:
        log_data["rows"] = rows

    if request_id:
        log_data["request_id"] = request_id

    # Add any additional context
    log_data.update(kwargs)

    log_event(**log_data)


# ============================================================================
# Context Manager for Timing
# ============================================================================


class LogTimer:
    """
    Context manager for timing operations and logging the result.

    Usage:
        with LogTimer("fetch_schedule", service="api", dataset="schedule"):
            df = fetch_schedule_data()
    """

    def __init__(self, operation: str, **log_context: Any):
        """
        Initialize timer.

        Args:
            operation: Operation name (will be logged as 'operation' key)
            **log_context: Additional context to include in log
        """
        self.operation = operation
        self.log_context = log_context
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> "LogTimer":
        """Start timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timer and log result."""
        self.end_time = time.perf_counter()
        assert self.start_time is not None, "Timer not started"
        duration_ms = (self.end_time - self.start_time) * 1000

        if exc_type is None:
            # Success
            log_event(
                event="operation_complete",
                operation=self.operation,
                duration_ms=round(duration_ms, 2),
                success=True,
                **self.log_context,
            )
        else:
            # Error occurred
            log_error(
                service=self.log_context.get("service", "unknown"),
                error=str(exc_val),
                error_type=exc_type.__name__ if exc_type else None,
                operation=self.operation,
                duration_ms=round(duration_ms, 2),
                **self.log_context,
            )
        # Note: Returning None (implicit) means don't suppress exception


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "log_event",
    "log_request",
    "log_error",
    "log_cache",
    "log_tool_call",
    "LogTimer",
]
