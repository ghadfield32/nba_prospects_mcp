"""
Auto-pagination and Token Management Wrappers for MCP Tools.

Provides intelligent pagination and token budgeting to prevent small LLMs from
running out of context. Automatically summarizes large datasets and provides
cursors for continued access.

Key Features:
    - Auto-pagination: Fetches data in chunks to stay under token budget
    - Token estimation: Cheap upper-bound calculation (rows × cols × 4)
    - Shape modes: 'array', 'records', 'summary' for different use cases
    - Cursor support: Continue fetching with next_cursor
    - Column pruning: Optional reduction to key columns only

Environment Variables:
    CBB_MAX_ROWS: Maximum rows before pagination (default: 2000)
    CBB_MAX_TOKENS: Maximum tokens before stopping (default: 8000)

Usage:
    from cbb_data.servers.mcp_wrappers import mcp_autopaginate, prune_to_key_columns

    @mcp_autopaginate
    def get_data(league, season, limit=None, offset=0, **kwargs):
        return get_dataset("schedule", {"league": league, "season": season}, limit=limit)

    # Auto-paginates and returns summary if too large
    result = get_data("NCAA-MBB", "2025", shape="summary")
"""

import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Configuration from environment
MAX_ROWS = int(os.getenv("CBB_MAX_ROWS", "2000"))
MAX_TOKENS = int(os.getenv("CBB_MAX_TOKENS", "8000"))


# ============================================================================
# Token Estimation
# ============================================================================


def estimate_tokens(rows: int, cols: int) -> int:
    """
    Estimate token count for a DataFrame.

    Uses a cheap upper-bound heuristic: rows × cols × 4
    This assumes ~4 tokens per cell (conservative for numbers, tight for long strings).

    Args:
        rows: Number of rows
        cols: Number of columns

    Returns:
        Estimated token count

    Examples:
        >>> estimate_tokens(100, 10)
        4000  # 100 rows × 10 cols × 4 tokens/cell

        >>> estimate_tokens(50, 20)
        4000  # 50 rows × 20 cols × 4 tokens/cell
    """
    return rows * cols * 4


# ============================================================================
# Column Pruning
# ============================================================================


def prune_to_key_columns(df: pd.DataFrame, dataset_id: str | None = None) -> pd.DataFrame:
    """
    Reduce DataFrame to key columns only for token efficiency.

    Key columns are determined by:
    1. Dataset-specific key columns (from registry) if dataset_id provided
    2. Common important columns (ID, name, date, score columns)
    3. First N columns if no metadata available

    Args:
        df: Input DataFrame
        dataset_id: Optional dataset identifier for smart pruning

    Returns:
        DataFrame with only key columns

    Examples:
        >>> df = pd.DataFrame({
        ...     "PLAYER_ID": [1, 2],
        ...     "PLAYER_NAME": ["Alice", "Bob"],
        ...     "PTS": [20, 15],
        ...     "OBSCURE_STAT": [0.5, 0.3]
        ... })
        >>> pruned = prune_to_key_columns(df, "player_game")
        >>> list(pruned.columns)
        ['PLAYER_ID', 'PLAYER_NAME', 'PTS']  # OBSCURE_STAT removed
    """
    if df.empty:
        return df

    # Priority 1: Dataset-specific key columns (if available)
    if dataset_id:
        # Try to get dataset metadata
        try:
            from cbb_data.catalog.registry import DatasetRegistry

            entry = DatasetRegistry.get(dataset_id)

            # Combine keys + sample_columns as "important"
            important = set(entry.get("keys", [])) | set(entry.get("sample_columns", []))

            # Filter to columns that exist in df
            key_cols = [c for c in df.columns if c in important]

            if key_cols:
                logger.debug(
                    f"Pruned {dataset_id} from {len(df.columns)} to {len(key_cols)} key columns"
                )
                return df[key_cols]
        except Exception as e:
            logger.debug(f"Could not get dataset metadata for {dataset_id}: {e}")

    # Priority 2: Common important column patterns
    important_patterns = [
        # IDs
        "ID",
        "_ID",
        # Names
        "NAME",
        "PLAYER",
        "TEAM",
        # Dates/Time
        "DATE",
        "SEASON",
        "GAME",
        # Scores/Stats
        "PTS",
        "SCORE",
        "WIN",
        "LOSS",
        "REB",
        "AST",
        "FG",
        "FT",
        # Location
        "HOME",
        "AWAY",
    ]

    important_cols = []
    for col in df.columns:
        col_upper = col.upper()
        if any(pattern in col_upper for pattern in important_patterns):
            important_cols.append(col)

    if important_cols:
        logger.debug(
            f"Pruned from {len(df.columns)} to {len(important_cols)} columns using patterns"
        )
        return df[important_cols]

    # Priority 3: Fallback - keep first 10 columns
    max_cols = 10
    if len(df.columns) > max_cols:
        logger.debug(f"Pruned from {len(df.columns)} to {max_cols} columns (fallback)")
        return df.iloc[:, :max_cols]

    return df


# ============================================================================
# Auto-Pagination Decorator
# ============================================================================


def mcp_autopaginate(get_df_fn: Callable) -> Callable:
    """
    Decorator that adds auto-pagination and token management to dataset functions.

    Features:
        - Automatically paginates large results to stay under token budget
        - Supports 'summary' shape for ultra-compact responses
        - Provides cursors for continued access
        - Integrates with column pruning

    The wrapped function must accept:
        - limit: int (optional) - rows to fetch per chunk
        - offset: int (optional) - starting row offset
        - shape: str (optional) - 'array', 'records', or 'summary'
        - cursor: int (optional) - continuation cursor
        - compact_columns: bool (optional) - enable column pruning

    Returns:
        Wrapped function that handles pagination automatically

    Examples:
        >>> @mcp_autopaginate
        ... def fetch_schedule(league, season, limit=None, offset=0):
        ...     return get_dataset("schedule", {"league": league, "season": season}, limit=limit)

        >>> # Fetch with auto-pagination
        >>> result = fetch_schedule("NCAA-MBB", "2025")
        >>> result["truncated"]  # True if more data available
        True
        >>> result["next_cursor"]  # Cursor for next page
        500

        >>> # Fetch summary instead of full data
        >>> summary = fetch_schedule("NCAA-MBB", "2025", shape="summary")
        >>> summary["rows_returned"]
        5000
        >>> summary["stats"]  # Column statistics
        {"HOME_SCORE": {"min": 45, "max": 120}}
    """

    @wraps(get_df_fn)
    def wrapper(
        *args: Any,
        shape: str = "array",
        limit: int | None = None,
        cursor: int | None = None,
        offset: int | None = None,
        compact_columns: bool = False,
        dataset_id: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame | dict[str, Any]:
        """
        Auto-paginating wrapper for dataset functions.

        Args:
            *args: Positional arguments for wrapped function
            shape: Output shape - 'array', 'records', or 'summary'
            limit: User-specified limit (overrides auto-pagination)
            cursor: Continuation cursor from previous call
            offset: Manual offset (alternative to cursor)
            compact_columns: Enable column pruning for token efficiency
            dataset_id: Dataset identifier for smart column pruning
            **kwargs: Additional arguments for wrapped function

        Returns:
            Dict with data + metadata (shape != None) or DataFrame (legacy)
        """
        # Determine starting offset
        start_offset = cursor or offset or 0

        # Determine chunk size
        chunk_size = min(limit or MAX_ROWS, MAX_ROWS)

        # Pagination loop
        df_chunks = []
        total_tokens = 0
        current_offset = start_offset

        while True:
            # Fetch chunk
            try:
                chunk = get_df_fn(*args, limit=chunk_size, offset=current_offset, **kwargs)
            except TypeError:
                # Function doesn't support offset - fetch once and slice
                chunk = get_df_fn(*args, limit=chunk_size, **kwargs)
                if start_offset > 0 and not chunk.empty:
                    chunk = chunk.iloc[start_offset:]
                # Disable pagination for functions without offset support
                chunk_size = len(chunk)

            if chunk.empty:
                break

            # Apply column pruning if requested
            if compact_columns:
                chunk = prune_to_key_columns(chunk, dataset_id)

            df_chunks.append(chunk)

            # Estimate tokens
            tokens = estimate_tokens(len(chunk), len(chunk.columns))
            total_tokens += tokens

            current_offset += len(chunk)

            # Stop if we've hit limits
            if len(chunk) < chunk_size:  # No more data
                break
            if limit and current_offset >= start_offset + limit:  # User limit reached
                break
            if total_tokens >= MAX_TOKENS:  # Token budget exceeded
                logger.info(
                    f"Auto-pagination stopped at {total_tokens} tokens (limit: {MAX_TOKENS})"
                )
                break

        # Combine chunks
        if not df_chunks:
            df = pd.DataFrame()
        else:
            df = pd.concat(df_chunks, ignore_index=True)

        # Determine if truncated
        truncated = (len(df) == (limit or float("inf"))) or (total_tokens >= MAX_TOKENS)
        next_cursor = current_offset if truncated else None

        # Return based on shape
        if shape == "summary":
            # Ultra-compact summary mode
            return _create_summary(df, truncated, next_cursor)
        elif shape == "records":
            # Records mode (list of dicts)
            return {
                "columns": df.columns.tolist(),
                "data": df.to_dict(orient="records"),
                "truncated": truncated,
                "next_cursor": next_cursor,
                "row_count": len(df),
                "estimated_tokens": total_tokens,
            }
        elif shape == "array":
            # Array mode (default - most compact)
            return {
                "columns": df.columns.tolist(),
                "data": df.values.tolist(),
                "truncated": truncated,
                "next_cursor": next_cursor,
                "row_count": len(df),
                "estimated_tokens": total_tokens,
            }
        else:
            # Legacy mode - return DataFrame directly
            return df

    return wrapper


def _create_summary(df: pd.DataFrame, truncated: bool, next_cursor: int | None) -> dict[str, Any]:
    """
    Create ultra-compact summary of DataFrame.

    Includes:
        - Column list
        - Row count
        - Top N rows (sample)
        - Column statistics (for numeric columns)
        - Truncation status + cursor

    Args:
        df: DataFrame to summarize
        truncated: Whether data was truncated
        next_cursor: Cursor for continuation

    Returns:
        Summary dict
    """
    sample_size = min(20, len(df))
    sample = df.head(sample_size) if not df.empty else pd.DataFrame()

    # Calculate statistics for numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns
    stats = {}
    for col in numeric_cols:
        try:
            stats[col] = {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": float(df[col].mean()),
            }
        except Exception:
            pass  # Skip if stats fail

    return {
        "columns": df.columns.tolist(),
        "rows_returned": len(df),
        "sample": sample.to_dict(orient="records"),
        "sample_size": len(sample),
        "truncated": truncated,
        "next_cursor": next_cursor,
        "stats": stats,
    }


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "mcp_autopaginate",
    "prune_to_key_columns",
    "estimate_tokens",
    "MAX_ROWS",
    "MAX_TOKENS",
]
