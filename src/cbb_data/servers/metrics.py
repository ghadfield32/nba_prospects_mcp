"""
Prometheus Metrics for CBB Data Servers.

Provides comprehensive metrics collection for monitoring API performance,
cache efficiency, and tool usage.

Metrics Exposed:
    - cbb_tool_calls_total: Counter of tool calls by tool name
    - cbb_cache_hits_total: Counter of cache hits by dataset
    - cbb_cache_misses_total: Counter of cache misses by dataset
    - cbb_tool_latency_ms: Histogram of tool execution times
    - cbb_rows_returned: Histogram of rows returned per request
    - cbb_duckdb_size_mb: Gauge of DuckDB cache size
    - cbb_request_total: Counter of HTTP requests by endpoint and status
    - cbb_request_duration_seconds: Histogram of request duration

Usage:
    from cbb_data.servers.metrics import (
        TOOL_CALLS,
        CACHE_HITS,
        LATENCY_MS,
        track_tool_call,
        track_cache_hit
    )

    # Increment counters
    TOOL_CALLS.labels(tool="get_schedule").inc()

    # Track histogram values
    LATENCY_MS.labels(tool="get_schedule").observe(125.5)

    # Or use convenience functions
    track_tool_call("get_schedule", duration_ms=125.5, rows=50)
    track_cache_hit("schedule", "NCAA-MBB", "2025")
"""

import logging
import os
from typing import Any

# Optional Prometheus dependency - gracefully degrade if not installed
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore[assignment,misc]
    Histogram = None  # type: ignore[assignment,misc]
    Gauge = None  # type: ignore[assignment,misc]
    generate_latest = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain"
    REGISTRY = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Check if metrics are enabled via environment variable
METRICS_ENABLED = os.getenv("CBB_METRICS_ENABLED", "true").lower() == "true"

# ============================================================================
# Metric Definitions
# ============================================================================

# Initialize metrics if Prometheus is available and enabled
if PROMETHEUS_AVAILABLE and METRICS_ENABLED:
    # Tool call counters
    TOOL_CALLS = Counter(
        "cbb_tool_calls_total",
        "Total number of tool calls",
        ["tool", "service"],  # labels: tool name, service (mcp/rest/api)
    )

    # Cache metrics
    CACHE_HITS = Counter(
        "cbb_cache_hits_total", "Total number of cache hits", ["dataset", "league"]
    )

    CACHE_MISSES = Counter(
        "cbb_cache_misses_total", "Total number of cache misses", ["dataset", "league"]
    )

    CACHE_SAVES = Counter(
        "cbb_cache_saves_total", "Total number of cache saves", ["dataset", "league"]
    )

    # Latency histograms
    LATENCY_MS = Histogram(
        "cbb_tool_latency_ms",
        "Tool execution latency in milliseconds",
        ["tool", "service"],
        buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],  # ms
    )

    REQUEST_DURATION = Histogram(
        "cbb_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint", "status"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],  # seconds
    )

    # Data size metrics
    ROWS_RETURNED = Histogram(
        "cbb_rows_returned",
        "Number of rows returned per request",
        ["dataset", "league"],
        buckets=[1, 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    )

    # DuckDB cache size gauge
    DUCKDB_SIZE_MB = Gauge("cbb_duckdb_size_mb", "DuckDB cache file size in megabytes")

    # HTTP request counters
    REQUEST_TOTAL = Counter(
        "cbb_request_total", "Total HTTP requests", ["method", "endpoint", "status"]
    )

    # Error counters
    ERROR_TOTAL = Counter("cbb_error_total", "Total errors", ["service", "error_type"])

    logger.info("✓ Prometheus metrics initialized (CBB_METRICS_ENABLED=true)")

else:
    # Create no-op metrics if Prometheus not available or disabled
    class NoOpMetric:
        """No-op metric that does nothing."""

        def labels(self, **kwargs: Any) -> "NoOpMetric":
            return self

        def inc(self, amount: int = 1) -> None:
            pass

        def observe(self, amount: float) -> None:
            pass

        def set(self, value: float) -> None:
            pass

    TOOL_CALLS = NoOpMetric()  # type: ignore[assignment]
    CACHE_HITS = NoOpMetric()  # type: ignore[assignment]
    CACHE_MISSES = NoOpMetric()  # type: ignore[assignment]
    CACHE_SAVES = NoOpMetric()  # type: ignore[assignment]
    LATENCY_MS = NoOpMetric()  # type: ignore[assignment]
    REQUEST_DURATION = NoOpMetric()  # type: ignore[assignment]
    ROWS_RETURNED = NoOpMetric()  # type: ignore[assignment]
    DUCKDB_SIZE_MB = NoOpMetric()  # type: ignore[assignment]
    REQUEST_TOTAL = NoOpMetric()  # type: ignore[assignment]
    ERROR_TOTAL = NoOpMetric()  # type: ignore[assignment]

    if not PROMETHEUS_AVAILABLE:
        logger.warning(
            "Prometheus client not installed - metrics disabled. "
            "Install with: pip install prometheus-client"
        )
    else:
        logger.info("Prometheus metrics disabled (CBB_METRICS_ENABLED=false)")


# ============================================================================
# Convenience Functions
# ============================================================================


def track_tool_call(
    tool: str,
    service: str = "mcp",
    duration_ms: float | None = None,
    rows: int | None = None,
    dataset: str | None = None,
    league: str | None = None,
) -> None:
    """
    Track a tool call with metrics.

    Args:
        tool: Tool name
        service: Service name (mcp, rest, api)
        duration_ms: Execution duration in milliseconds
        rows: Number of rows returned
        dataset: Dataset ID (for rows histogram)
        league: League name (for rows histogram)

    Example:
        >>> track_tool_call("get_schedule", duration_ms=125.5, rows=50, dataset="schedule", league="NCAA-MBB")
    """
    # Increment tool call counter
    TOOL_CALLS.labels(tool=tool, service=service).inc()

    # Track latency if provided
    if duration_ms is not None:
        LATENCY_MS.labels(tool=tool, service=service).observe(duration_ms)

    # Track rows returned if provided
    if rows is not None and dataset and league:
        ROWS_RETURNED.labels(dataset=dataset, league=league).observe(rows)


def track_cache_hit(dataset: str, league: str, duration_ms: float | None = None) -> None:
    """
    Track a cache hit.

    Args:
        dataset: Dataset ID
        league: League name
        duration_ms: Load duration in milliseconds (optional)

    Example:
        >>> track_cache_hit("schedule", "NCAA-MBB", duration_ms=0.5)
    """
    CACHE_HITS.labels(dataset=dataset, league=league).inc()


def track_cache_miss(dataset: str, league: str) -> None:
    """
    Track a cache miss.

    Args:
        dataset: Dataset ID
        league: League name

    Example:
        >>> track_cache_miss("schedule", "NCAA-MBB")
    """
    CACHE_MISSES.labels(dataset=dataset, league=league).inc()


def track_cache_save(dataset: str, league: str, rows: int) -> None:
    """
    Track a cache save operation.

    Args:
        dataset: Dataset ID
        league: League name
        rows: Number of rows saved

    Example:
        >>> track_cache_save("schedule", "NCAA-MBB", rows=150)
    """
    CACHE_SAVES.labels(dataset=dataset, league=league).inc()


def track_http_request(method: str, endpoint: str, status: int, duration_seconds: float) -> None:
    """
    Track an HTTP request.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint
        status: HTTP status code
        duration_seconds: Request duration in seconds

    Example:
        >>> track_http_request("POST", "/datasets/player_game", 200, 0.125)
    """
    REQUEST_TOTAL.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint, status=str(status)).observe(
        duration_seconds
    )


def track_error(service: str, error_type: str) -> None:
    """
    Track an error occurrence.

    Args:
        service: Service name (rest, mcp, api)
        error_type: Error class name (ValueError, KeyError, etc.)

    Example:
        >>> track_error("mcp", "ValueError")
    """
    ERROR_TOTAL.labels(service=service, error_type=error_type).inc()


def update_cache_size(size_mb: float) -> None:
    """
    Update DuckDB cache size gauge.

    Args:
        size_mb: Cache size in megabytes

    Example:
        >>> update_cache_size(125.5)
    """
    DUCKDB_SIZE_MB.set(size_mb)


def get_metrics_snapshot() -> dict:
    """
    Get a snapshot of current metrics for LLMs.

    Returns a compact summary of key metrics suitable for MCP tool responses.

    Returns:
        Dict with metrics summary

    Example:
        >>> snapshot = get_metrics_snapshot()
        >>> print(snapshot)
        {
            "cache_hit_rate": "85.3%",
            "avg_latency_ms": 125.5,
            "total_requests": 1523,
            "cache_size_mb": 45.2
        }
    """
    if not PROMETHEUS_AVAILABLE or not METRICS_ENABLED:
        return {"metrics_enabled": False}

    # This is a simplified snapshot - in production, you'd query the actual metric values
    # from REGISTRY. For now, return a placeholder.
    return {
        "metrics_enabled": True,
        "note": "Use GET /metrics endpoint for full Prometheus metrics",
    }


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Metrics
    "TOOL_CALLS",
    "CACHE_HITS",
    "CACHE_MISSES",
    "CACHE_SAVES",
    "LATENCY_MS",
    "REQUEST_DURATION",
    "ROWS_RETURNED",
    "DUCKDB_SIZE_MB",
    "REQUEST_TOTAL",
    "ERROR_TOTAL",
    # Tracking functions
    "track_tool_call",
    "track_cache_hit",
    "track_cache_miss",
    "track_cache_save",
    "track_http_request",
    "track_error",
    "update_cache_size",
    "get_metrics_snapshot",
    # Prometheus exports (for /metrics endpoint)
    "generate_latest",
    "CONTENT_TYPE_LATEST",
    "PROMETHEUS_AVAILABLE",
    "METRICS_ENABLED",
]
