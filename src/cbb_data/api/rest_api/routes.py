"""
Route handlers for REST API endpoints.

All routes are thin wrappers around the existing get_dataset() function,
ensuring we reuse all existing logic without duplication.
"""

import io
import json
import logging
import time
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import Response, StreamingResponse

# Import existing library functions - NO modifications needed!
from cbb_data.api.datasets import get_dataset, get_recent_games, list_datasets

# Import metrics module for /metrics endpoint
try:
    from cbb_data.servers.metrics import (
        CONTENT_TYPE_LATEST,
        PROMETHEUS_AVAILABLE,
        generate_latest,
        get_metrics_snapshot,
    )

    METRICS_AVAILABLE = PROMETHEUS_AVAILABLE
except ImportError:
    METRICS_AVAILABLE = False
    generate_latest = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain"

from .models import (
    DatasetInfo,
    DatasetMetadata,
    DatasetRequest,
    DatasetResponse,
    DatasetsListResponse,
    HealthResponse,
    LNBErrorResponse,
    LNBReadinessResponse,
    LNBSeasonReadiness,
    LNBValidationStatusResponse,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================


def _generate_ndjson_stream(df: pd.DataFrame) -> Generator[str, None, None]:
    """
    Generate NDJSON (newline-delimited JSON) stream for DataFrame.

    Each row is serialized as a JSON object on its own line.
    This allows LLMs to process results incrementally without loading
    entire response into memory.

    Args:
        df: Pandas DataFrame to stream

    Yields:
        JSON lines (one per row)

    Example output:
        {"name": "John", "pts": 24}
        {"name": "Mary", "pts": 22}
        ...
    """
    if df is None or df.empty:
        return

    # Convert to records (list of dicts) for efficient streaming
    for record in df.to_dict(orient="records"):
        yield json.dumps(record) + "\n"


def _dataframe_to_response_data(
    df: pd.DataFrame, output_format: str
) -> tuple[list[Any] | str | bytes | list[dict[str, Any]], list[str] | None]:
    """
    Convert DataFrame to response format.

    Args:
        df: Pandas DataFrame to convert
        output_format: Output format ('json', 'csv', 'parquet', 'records', 'ndjson')

    Returns:
        Tuple of (data, columns) where:
        - data: Response data in requested format (list[list], str, bytes, or list[dict])
        - columns: Column names (None for self-describing formats like csv/parquet/ndjson)

    Supported formats:
        - json: Array of arrays (most compact for JSON)
        - csv: Comma-separated string (easy export)
        - parquet: Compressed binary (5-10x smaller, base64-encoded)
        - records: Array of objects (most readable)
        - ndjson: Newline-delimited JSON (streaming, one object per line)
    """
    if df is None or df.empty:
        return [], []

    columns: list[str] | None = df.columns.tolist()
    data: list[Any] | str | bytes | list[dict[str, Any]]

    if output_format == "json":
        # Array of arrays format (most compact)
        data = df.values.tolist()
    elif output_format == "csv":
        # CSV string (for easy export)
        csv_string = df.to_csv(index=False)
        data = csv_string
        columns = None  # CSV includes headers
    elif output_format == "parquet":
        # Parquet binary format (5-10x smaller than CSV, 10-100x faster parsing)
        try:
            buffer = io.BytesIO()
            df.to_parquet(
                buffer,
                engine="pyarrow",
                compression="zstd",  # Best balance of speed/size
                index=False,
            )
            data = buffer.getvalue()  # bytes (auto base64-encoded by FastAPI)
            columns = None  # Parquet includes schema
        except Exception as e:
            logger.error(f"Failed to serialize to parquet: {str(e)}", exc_info=True)
            raise ValueError(
                f"Parquet serialization failed: {str(e)}. Ensure pyarrow is installed."
            ) from e
    elif output_format == "records":
        # Array of objects (most readable)
        data = df.to_dict(orient="records")
        columns = None  # Each record has keys
    elif output_format == "ndjson":
        # NDJSON format (newline-delimited JSON, one object per line)
        # This is handled specially in the route handlers for streaming
        data = df.to_dict(orient="records")
        columns = None  # Each record has keys
    else:
        raise ValueError(f"Unsupported output_format: {output_format}")

    return data, columns


# ============================================================================
# Health Check Endpoint
# ============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Check if the API server is running and healthy",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status and version information.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow(),
        services={"api": "healthy", "cache": "healthy", "data_sources": "healthy"},
    )


# ============================================================================
# Dataset Listing Endpoint
# ============================================================================


@router.get(
    "/datasets",
    response_model=DatasetsListResponse,
    tags=["Datasets"],
    summary="List all datasets",
    description="Get metadata about all available datasets",
)
async def list_all_datasets() -> DatasetsListResponse:
    """
    List all available datasets with their metadata.

    Uses the existing list_datasets() function - no custom logic needed!
    """
    try:
        # Call existing library function
        datasets_raw = list_datasets()

        # Convert to response models
        datasets = [
            DatasetInfo(
                id=ds["id"],
                name=ds.get("id", "").replace("_", " ").title(),
                description=ds.get("description", ""),
                keys=ds.get("keys", []),
                supported_filters=ds.get("supports", []),
                supported_leagues=ds.get("leagues", []),
                data_sources=ds.get("sources", []),
                sample_columns=ds.get("sample_columns", []),
            )
            for ds in datasets_raw
        ]

        return DatasetsListResponse(datasets=datasets, count=len(datasets))

    except Exception as e:
        logger.error(f"Error listing datasets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list datasets: {str(e)}",
        ) from e


# ============================================================================
# Dataset Query Endpoint
# ============================================================================


@router.post(
    "/datasets/{dataset_id}",
    tags=["Datasets"],
    summary="Query a dataset",
    description="Fetch data from a specific dataset with filters. Supports streaming with output_format=ndjson",
)
async def query_dataset(
    dataset_id: str = Path(
        ...,
        description="Dataset ID (e.g., 'player_game', 'schedule', 'pbp')",
        examples=["player_game", "schedule", "play_by_play"],
    ),
    request: DatasetRequest = DatasetRequest(),
) -> StreamingResponse | DatasetResponse:
    """
    Query a dataset with filters.

    This endpoint is a thin wrapper around get_dataset() - all filtering,
    validation, caching, and data fetching logic is handled by the existing
    library code.

    Args:
        dataset_id: ID of dataset to query
        request: Query parameters (filters, limit, offset, output_format)

    Returns:
        Dataset rows with optional metadata

    Raises:
        400: Invalid filters or dataset ID
        404: Dataset not found
        500: Internal server error
    """
    start_time = time.time()

    try:
        # Log the request
        logger.info(f"Dataset query: {dataset_id} with filters {request.filters}")

        # Call existing get_dataset() function - NO CHANGES NEEDED!
        df = get_dataset(
            grouping=dataset_id,
            filters=request.filters,
            columns=None,  # Return all columns
            limit=request.limit,
            as_format="pandas",  # We'll convert to requested format
            name_resolver=None,  # Use default name resolution
            force_fresh=False,  # Use cache when available
        )

        # Handle pagination with offset
        if request.offset and request.offset > 0:
            df = df.iloc[request.offset :]

        # Check if NDJSON streaming is requested
        if request.output_format == "ndjson":
            # Return streaming response for NDJSON
            logger.info(
                f"Dataset query (streaming): {dataset_id}, "
                f"{len(df) if df is not None else 0} rows"
            )
            return StreamingResponse(
                _generate_ndjson_stream(df),
                media_type="application/x-ndjson",
                headers={
                    "X-Dataset-ID": dataset_id,
                    "X-Row-Count": str(len(df) if df is not None else 0),
                    "X-Execution-Time-MS": f"{(time.time() - start_time) * 1000:.2f}",
                },
            )

        # Convert DataFrame to response format (non-streaming)
        data, columns = _dataframe_to_response_data(df, request.output_format)

        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000

        # Build metadata if requested
        metadata = None
        if request.include_metadata:
            metadata = DatasetMetadata(
                dataset_id=dataset_id,
                filters_applied=request.filters,
                row_count=len(data) if isinstance(data, list) else 0,
                total_rows=len(df) if df is not None else 0,
                execution_time_ms=round(execution_time, 2),
                cached=execution_time < 100,  # Heuristic: <100ms likely cached
                cache_key=None,  # Not exposed in current implementation
                timestamp=datetime.utcnow(),
            )

        logger.info(
            f"Dataset query completed: {dataset_id}, "
            f"{metadata.row_count if metadata else 0} rows, "
            f"{execution_time:.2f}ms"
        )

        return DatasetResponse(data=data, columns=columns, metadata=metadata)

    except KeyError as e:
        # Dataset not found
        logger.warning(f"Dataset not found: {dataset_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except ValueError as e:
        # Invalid filters
        logger.warning(f"Invalid filters for {dataset_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    except Exception as e:
        # Unexpected error
        logger.error(f"Error querying dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query dataset: {str(e)}",
        ) from e


# ============================================================================
# Recent Games Convenience Endpoint
# ============================================================================


@router.get(
    "/recent-games/{league}",
    response_model=DatasetResponse,
    tags=["Convenience"],
    summary="Get recent games",
    description="Convenience endpoint for fetching recent games without date filters",
)
async def get_recent_games_endpoint(
    league: str = Path(
        ..., description="League identifier", examples=["NCAA-MBB", "NCAA-WBB", "EuroLeague"]
    ),
    days: int = Query(
        default=2, description="Number of days to look back (1 = today only)", ge=1, le=30
    ),
    teams: str = Query(default=None, description="Comma-separated list of team names (optional)"),
    division: str = Query(default=None, description="Division filter for NCAA (D1, D2, D3, all)"),
    output_format: str = Query(
        default="json",
        description="Output format (json, csv, parquet, records, ndjson)",
        pattern="^(json|csv|parquet|records|ndjson)$",
    ),
) -> DatasetResponse:
    """
    Get recent games for a league.

    Convenience wrapper around get_recent_games() function. Automatically
    calculates date range from today backwards.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        days: Number of days to look back (default: 2)
        teams: Optional comma-separated team names
        division: Optional division filter (NCAA only)
        output_format: Output format (json, csv, parquet, records)

    Returns:
        Recent games schedule with scores

    Examples:
        GET /recent-games/NCAA-MBB?days=2
        GET /recent-games/NCAA-MBB?days=7&teams=Duke,UNC
        GET /recent-games/EuroLeague?days=3&output_format=parquet
    """
    start_time = time.time()

    try:
        # Parse teams if provided
        teams_list = None
        if teams:
            teams_list = [t.strip() for t in teams.split(",")]

        # Call existing get_recent_games() function - NO CHANGES!
        df = get_recent_games(
            league=league, days=days, teams=teams_list, Division=division, force_fresh=False
        )

        # Convert to response format
        data, columns = _dataframe_to_response_data(df, output_format)

        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000

        # Build metadata
        metadata = DatasetMetadata(
            dataset_id="schedule",
            filters_applied={
                "league": league,
                "days": days,
                "teams": teams_list,
                "division": division,
            },
            row_count=len(data) if isinstance(data, list) else 0,
            total_rows=len(df) if df is not None else 0,
            execution_time_ms=round(execution_time, 2),
            cached=execution_time < 100,
            timestamp=datetime.utcnow(),
        )

        return DatasetResponse(data=data, columns=columns, metadata=metadata)

    except Exception as e:
        logger.error(f"Error fetching recent games for {league}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent games: {str(e)}",
        ) from e


# ============================================================================
# Dataset Info Endpoint
# ============================================================================


@router.get(
    "/datasets/{dataset_id}/info",
    response_model=DatasetInfo,
    tags=["Datasets"],
    summary="Get dataset info",
    description="Get metadata about a specific dataset",
)
async def get_dataset_info(
    dataset_id: str = Path(..., description="Dataset ID", examples=["player_game", "schedule"]),
) -> DatasetInfo:
    """
    Get information about a specific dataset.

    Returns metadata including supported filters, leagues, and sample columns.

    Args:
        dataset_id: ID of dataset to get info for

    Returns:
        Dataset metadata

    Raises:
        404: Dataset not found
    """
    try:
        # Get all datasets
        datasets_raw = list_datasets()

        # Find the requested dataset
        dataset = next((ds for ds in datasets_raw if ds["id"] == dataset_id), None)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset '{dataset_id}' not found"
            )

        # Convert to response model
        return DatasetInfo(
            id=dataset["id"],
            name=dataset.get("id", "").replace("_", " ").title(),
            description=dataset.get("description", ""),
            keys=dataset.get("keys", []),
            supported_filters=dataset.get("supports", []),
            supported_leagues=dataset.get("leagues", []),
            data_sources=dataset.get("sources", []),
            sample_columns=dataset.get("sample_columns", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset info: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dataset info: {str(e)}",
        ) from e


# ============================================================================
# Schema Endpoints (Self-Documentation)
# ============================================================================


@router.get(
    "/schema/datasets",
    tags=["Schema"],
    summary="Get dataset schemas",
    description="Self-documenting endpoint that returns all available datasets with their metadata",
)
async def get_datasets_schema() -> dict[str, Any]:
    """
    Get comprehensive schema for all datasets.

    Returns all available datasets with metadata including:
    - Dataset IDs and descriptions
    - Supported filters and leagues
    - Sample columns
    - Data sources

    This endpoint allows LLMs to auto-discover API capabilities without reading docs.

    Returns:
        Dictionary with dataset schemas

    Examples:
        GET /schema/datasets
    """
    try:
        datasets_raw = list_datasets()

        # Convert to comprehensive schema format
        schemas = {}
        for ds in datasets_raw:
            schemas[ds["id"]] = {
                "id": ds["id"],
                "name": ds.get("id", "").replace("_", " ").title(),
                "description": ds.get("description", ""),
                "keys": ds.get("keys", []),
                "supported_filters": ds.get("supports", []),
                "supported_leagues": ds.get("leagues", []),
                "data_sources": ds.get("sources", []),
                "sample_columns": ds.get("sample_columns", []),
                "endpoint": f"/datasets/{ds['id']}",
            }

        return {
            "schemas": schemas,
            "count": len(schemas),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating dataset schemas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate schemas: {str(e)}",
        ) from e


@router.get(
    "/schema/filters",
    tags=["Schema"],
    summary="Get available filters",
    description="Returns all available filter options for querying datasets",
)
async def get_filters_schema() -> dict[str, Any]:
    """
    Get comprehensive schema for all available filters.

    Returns filter options including:
    - Filter names and types
    - Accepted values/formats
    - Natural language support
    - Examples

    This helps LLMs understand what filters are available and how to use them.

    Returns:
        Dictionary with filter schemas

    Examples:
        GET /schema/filters
    """
    try:
        # Define all available filters with their schemas
        filters_schema = {
            "league": {
                "type": "string",
                "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                "required": True,
                "description": "League identifier",
                "examples": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
            },
            "season": {
                "type": "string",
                "format": "YYYY or natural language",
                "natural_language": True,
                "accepted_values": [
                    "YYYY format (e.g., '2025')",
                    "YYYY-YY format (e.g., '2024-25')",
                    "Natural language: 'this season', 'last season', 'current season'",
                ],
                "description": "Season year. Basketball seasons named by ending year (2024-25 = '2025')",
                "examples": ["2025", "2024-25", "this season", "last season"],
            },
            "team": {
                "type": "array[string]",
                "description": "List of team names to filter",
                "examples": [["Duke"], ["Duke", "UNC"], ["Michigan State"]],
            },
            "player": {
                "type": "array[string]",
                "description": "List of player names to filter",
                "examples": [["Cooper Flagg"], ["Caitlin Clark"], ["John Doe"]],
            },
            "date": {
                "type": "string or object",
                "format": "YYYY-MM-DD or natural language",
                "natural_language": True,
                "accepted_values": [
                    "YYYY-MM-DD format (e.g., '2025-01-15')",
                    "Natural language: 'today', 'yesterday', '3 days ago'",
                    "Date range object: {start: 'YYYY-MM-DD', end: 'YYYY-MM-DD'}",
                ],
                "description": "Single date or date range",
                "examples": [
                    "2025-01-15",
                    "yesterday",
                    {"start": "2025-01-01", "end": "2025-01-31"},
                ],
            },
            "date_from": {
                "type": "string",
                "format": "YYYY-MM-DD or natural language",
                "natural_language": True,
                "accepted_values": [
                    "YYYY-MM-DD format",
                    "Natural language: 'yesterday', 'last week', '3 days ago'",
                ],
                "description": "Start date for date range filtering",
                "examples": ["2025-01-01", "yesterday", "last week"],
            },
            "date_to": {
                "type": "string",
                "format": "YYYY-MM-DD or natural language",
                "natural_language": True,
                "description": "End date for date range filtering",
                "examples": ["2025-01-31", "today"],
            },
            "game_ids": {
                "type": "array[string]",
                "required_for": ["play_by_play", "shots"],
                "description": "List of game IDs",
                "examples": [["401635571"], ["401635571", "401635572"]],
            },
            "per_mode": {
                "type": "string",
                "enum": ["Totals", "PerGame", "Per40"],
                "default": "Totals",
                "description": "Aggregation mode for season stats",
                "examples": ["Totals", "PerGame", "Per40"],
                "recommendations": {
                    "Totals": "Cumulative stats (raw numbers)",
                    "PerGame": "Per-game averages (best for comparisons)",
                    "Per40": "Per 40 minutes (normalizes playing time)",
                },
            },
            "Division": {
                "type": "string",
                "enum": ["D1", "D2", "D3", "all"],
                "description": "NCAA division filter",
                "examples": ["D1", "D2", "D3", "all"],
            },
            "limit": {
                "type": "integer",
                "default": 100,
                "min": 1,
                "max": 10000,
                "description": "Maximum number of rows to return",
                "examples": [10, 100, 1000],
            },
            "compact": {
                "type": "boolean",
                "default": False,
                "description": "Return arrays instead of markdown (saves ~70% tokens)",
                "examples": [True, False],
                "recommendation": "Use compact=True for queries returning >50 rows",
            },
        }

        return {
            "filters": filters_schema,
            "count": len(filters_schema),
            "natural_language_support": {
                "dates": ["yesterday", "today", "last week", "3 days ago", "last month"],
                "seasons": ["this season", "last season", "current season", "2024-25"],
                "days": ["today", "yesterday", "last week", "last 5 days", "last month"],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating filters schema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate filters schema: {str(e)}",
        ) from e


@router.get(
    "/schema/tools",
    tags=["Schema"],
    summary="Get MCP tool schemas",
    description="Returns schemas for all MCP tools available via the MCP server",
)
async def get_tools_schema() -> dict[str, Any]:
    """
    Get comprehensive schema for all MCP tools.

    Returns tool schemas including:
    - Tool names and descriptions
    - Input parameters and types
    - Natural language support
    - Usage examples
    - LLM integration tips

    This allows LLMs to auto-discover MCP tool capabilities.

    Returns:
        Dictionary with MCP tool schemas

    Examples:
        GET /schema/tools
    """
    try:
        # Import MCP tools registry
        from cbb_data.servers.mcp.tools import TOOLS

        # Convert TOOLS registry to schema format
        tools_schema = {}
        for tool in TOOLS:
            # Extract schema with type assertion
            input_schema: dict[str, Any] = tool["inputSchema"]  # type: ignore[index,assignment]
            properties: dict[str, Any] = input_schema.get("properties", {})

            tools_schema[tool["name"]] = {  # type: ignore[index]
                "name": tool["name"],  # type: ignore[index]
                "description": tool["description"],  # type: ignore[index]
                "inputSchema": input_schema,
                "natural_language_support": {
                    "season": properties.get("season", {})
                    .get("description", "")
                    .find("natural language")
                    != -1,
                    "dates": properties.get("date_from", {})
                    .get("description", "")
                    .find("natural language")
                    != -1,
                    "days": properties.get("days", {})
                    .get("description", "")
                    .find("natural language")
                    != -1,
                },
                "compact_mode": "compact" in properties,
                "required_params": input_schema.get("required", []),
            }

        return {
            "tools": tools_schema,
            "count": len(tools_schema),
            "features": {
                "natural_language": True,
                "compact_mode": True,
                "type_validation": True,
                "token_efficiency": "~70% savings with compact=True",
            },
            "usage_tips": {
                "dates": "Use natural language like 'yesterday', 'last week' instead of calculating dates",
                "seasons": "Use 'this season', 'last season' instead of figuring out current year",
                "compact": "Always use compact=True for queries returning >50 rows to save tokens",
                "per_mode": "Use per_mode='PerGame' for fair player comparisons",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating tools schema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate tools schema: {str(e)}",
        ) from e


# ============================================================================
# LNB Data Readiness Endpoints
# ============================================================================


@router.get(
    "/lnb/readiness",
    response_model=LNBReadinessResponse,
    tags=["LNB"],
    summary="Check LNB data readiness",
    description="Get readiness status for all LNB seasons (≥95% coverage + 0 errors = ready for modeling)",
)
async def lnb_readiness_check() -> LNBReadinessResponse:
    """
    Check LNB data readiness for all tracked seasons.

    Returns readiness status including coverage percentages and error counts.
    Seasons are considered "ready for modeling" when they meet:
    - ≥95% coverage for both PBP and shots
    - Zero critical errors

    Returns:
        Readiness status for all seasons

    Examples:
        GET /lnb/readiness
    """
    try:
        # Import validation functions (lazy import to avoid startup overhead)
        import json
        from pathlib import Path

        # Load cached validation status from disk
        data_dir = Path(__file__).parents[4] / "data" / "raw" / "lnb"
        status_file = data_dir / "lnb_last_validation.json"

        if not status_file.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Validation has not been run yet. Please run validation first: "
                "uv run python tools/lnb/validate_and_monitor_coverage.py",
            )

        with open(status_file) as f:
            validation_data = json.load(f)

        # Convert to response model
        seasons = [
            LNBSeasonReadiness(
                season=s["season"],
                ready_for_modeling=s["ready_for_modeling"],
                pbp_coverage=s["pbp_coverage"],
                pbp_expected=s["pbp_expected"],
                pbp_pct=s["pbp_pct"],
                shots_coverage=s["shots_coverage"],
                shots_expected=s["shots_expected"],
                shots_pct=s["shots_pct"],
                num_critical_issues=s["num_critical_issues"],
            )
            for s in validation_data["seasons"]
        ]

        ready_seasons = [s.season for s in seasons if s.ready_for_modeling]

        return LNBReadinessResponse(
            checked_at=datetime.fromisoformat(validation_data["run_at"]),
            seasons=seasons,
            any_season_ready=len(ready_seasons) > 0,
            ready_seasons=ready_seasons,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking LNB readiness: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check LNB readiness: {str(e)}",
        ) from e


@router.get(
    "/lnb/validation-status",
    response_model=LNBValidationStatusResponse,
    tags=["LNB"],
    summary="Get LNB validation status",
    description="Get latest validation status including golden fixtures, API spot-checks, and quality metrics",
)
async def lnb_validation_status() -> LNBValidationStatusResponse:
    """
    Get latest LNB validation status.

    Returns comprehensive validation results including:
    - Golden fixtures regression testing (detects API schema changes)
    - API spot-check results (random sampling for drift detection)
    - Per-game consistency errors and warnings
    - Season readiness for modeling

    Returns:
        Complete validation status

    Examples:
        GET /lnb/validation-status
    """
    try:
        # Import validation functions (lazy import to avoid startup overhead)
        import json
        from pathlib import Path

        # Load cached validation status from disk
        data_dir = Path(__file__).parents[4] / "data" / "raw" / "lnb"
        status_file = data_dir / "lnb_last_validation.json"

        if not status_file.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Validation has not been run yet. Please run validation first: "
                "uv run python tools/lnb/validate_and_monitor_coverage.py",
            )

        with open(status_file) as f:
            validation_data = json.load(f)

        # Convert to response model
        seasons = [
            LNBSeasonReadiness(
                season=s["season"],
                ready_for_modeling=s["ready_for_modeling"],
                pbp_coverage=s["pbp_coverage"],
                pbp_expected=s["pbp_expected"],
                pbp_pct=s["pbp_pct"],
                shots_coverage=s["shots_coverage"],
                shots_expected=s["shots_expected"],
                shots_pct=s["shots_pct"],
                num_critical_issues=s["num_critical_issues"],
            )
            for s in validation_data["seasons"]
        ]

        return LNBValidationStatusResponse(
            run_at=datetime.fromisoformat(validation_data["run_at"]),
            golden_fixtures_passed=validation_data["golden_fixtures_passed"],
            golden_failures=validation_data["golden_failures"],
            api_spotcheck_passed=validation_data["api_spotcheck_passed"],
            api_discrepancies=validation_data["api_discrepancies"],
            consistency_errors=validation_data["consistency_errors"],
            consistency_warnings=validation_data["consistency_warnings"],
            ready_for_live=validation_data["ready_for_live"],
            seasons=seasons,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LNB validation status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get LNB validation status: {str(e)}",
        ) from e


# ============================================================================
# LNB Season Readiness Guard (Decorator)
# ============================================================================


def require_lnb_season_ready(season: str) -> None:
    """
    Guard decorator/function to check if LNB season is ready for modeling.

    Raises HTTPException with 409 Conflict if season is not ready.

    Args:
        season: Season to check (e.g., "2023-2024")

    Raises:
        HTTPException: 409 Conflict if season not ready
        HTTPException: 503 Service Unavailable if validation not run
        HTTPException: 404 Not Found if season not tracked
    """
    try:
        import json
        from pathlib import Path

        # Load cached validation status from disk
        data_dir = Path(__file__).parents[4] / "data" / "raw" / "lnb"
        status_file = data_dir / "lnb_last_validation.json"

        if not status_file.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Validation has not been run yet. Please run validation first: "
                "uv run python tools/lnb/validate_and_monitor_coverage.py",
            )

        with open(status_file) as f:
            validation_data = json.load(f)

        # Find the requested season
        season_data = next((s for s in validation_data["seasons"] if s["season"] == season), None)

        if not season_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Season {season} is not tracked. Available seasons: "
                f"{[s['season'] for s in validation_data['seasons']]}",
            )

        # Check if ready
        if not season_data["ready_for_modeling"]:
            error_response = LNBErrorResponse(
                error_code="SEASON_NOT_READY",
                message=f"Season {season} is NOT READY for modeling "
                f"(Coverage: {season_data['pbp_pct']:.1f}%/{season_data['shots_pct']:.1f}%, "
                f"Errors: {season_data['num_critical_issues']})",
                season=season,
                detail={
                    "pbp_coverage": season_data["pbp_pct"],
                    "shots_coverage": season_data["shots_pct"],
                    "num_critical_issues": season_data["num_critical_issues"],
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_response.model_dump(),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking season readiness: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check season readiness: {str(e)}",
        ) from e


# ============================================================================
# Metrics Endpoint (Prometheus)
# ============================================================================


@router.get(
    "/metrics",
    tags=["Observability"],
    summary="Get Prometheus metrics",
    description="Prometheus-compatible metrics endpoint for monitoring",
)
async def get_metrics() -> Response:
    """
    Get Prometheus metrics.

    Exposes metrics in Prometheus text format for scraping by monitoring systems.

    Metrics include:
        - cbb_tool_calls_total: Tool call counters
        - cbb_cache_hits_total: Cache hit counters
        - cbb_cache_misses_total: Cache miss counters
        - cbb_tool_latency_ms: Tool execution latency histograms
        - cbb_rows_returned: Rows returned histograms
        - cbb_duckdb_size_mb: DuckDB cache size gauge
        - cbb_request_total: HTTP request counters
        - cbb_request_duration_seconds: Request duration histograms
        - cbb_error_total: Error counters

    Returns:
        Prometheus text format metrics

    Examples:
        GET /metrics
    """
    if not METRICS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Metrics not available. Install prometheus-client: pip install prometheus-client",
        )

    try:
        # Generate Prometheus metrics text format
        metrics_data = generate_latest()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate metrics: {str(e)}",
        ) from e


@router.get(
    "/metrics/snapshot",
    tags=["Observability"],
    summary="Get metrics snapshot (JSON)",
    description="Get a compact JSON snapshot of key metrics for LLMs",
)
async def get_metrics_json() -> dict[str, Any]:
    """
    Get metrics snapshot in JSON format.

    Returns a compact summary of key metrics suitable for LLM consumption.

    Returns:
        JSON with metrics summary

    Examples:
        GET /metrics/snapshot
    """
    if not METRICS_AVAILABLE:
        return {
            "metrics_enabled": False,
            "message": "Metrics not available. Install prometheus-client: pip install prometheus-client",
        }

    try:
        snapshot = get_metrics_snapshot()
        return snapshot

    except Exception as e:
        logger.error(f"Error generating metrics snapshot: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate metrics snapshot: {str(e)}",
        ) from e
