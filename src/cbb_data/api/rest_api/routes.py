"""
Route handlers for REST API endpoints.

All routes are thin wrappers around the existing get_dataset() function,
ensuring we reuse all existing logic without duplication.
"""

import time
import logging
import io
from typing import Any, Dict, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query, status
import pandas as pd

# Import existing library functions - NO modifications needed!
from cbb_data.api.datasets import get_dataset, list_datasets, get_recent_games

from .models import (
    DatasetRequest,
    DatasetResponse,
    DatasetMetadata,
    DatasetInfo,
    DatasetsListResponse,
    HealthResponse,
    RecentGamesRequest,
    ErrorResponse
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def _dataframe_to_response_data(
    df: pd.DataFrame,
    output_format: str
) -> tuple[List[Any], List[str]]:
    """
    Convert DataFrame to response format.

    Args:
        df: Pandas DataFrame to convert
        output_format: Output format ('json', 'csv', 'parquet', 'records')

    Returns:
        Tuple of (data, columns) where:
        - data: Response data in requested format (List, str, or bytes)
        - columns: Column names (None for self-describing formats like csv/parquet)

    Supported formats:
        - json: Array of arrays (most compact for JSON)
        - csv: Comma-separated string (easy export)
        - parquet: Compressed binary (5-10x smaller, base64-encoded)
        - records: Array of objects (most readable)
    """
    if df is None or df.empty:
        return [], []

    columns = df.columns.tolist()

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
                engine='pyarrow',
                compression='zstd',  # Best balance of speed/size
                index=False
            )
            data = buffer.getvalue()  # bytes (auto base64-encoded by FastAPI)
            columns = None  # Parquet includes schema
        except Exception as e:
            logger.error(f"Failed to serialize to parquet: {str(e)}", exc_info=True)
            raise ValueError(f"Parquet serialization failed: {str(e)}. Ensure pyarrow is installed.")
    elif output_format == "records":
        # Array of objects (most readable)
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
    description="Check if the API server is running and healthy"
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
        services={
            "api": "healthy",
            "cache": "healthy",
            "data_sources": "healthy"
        }
    )


# ============================================================================
# Dataset Listing Endpoint
# ============================================================================

@router.get(
    "/datasets",
    response_model=DatasetsListResponse,
    tags=["Datasets"],
    summary="List all datasets",
    description="Get metadata about all available datasets"
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
                sample_columns=ds.get("sample_columns", [])
            )
            for ds in datasets_raw
        ]

        return DatasetsListResponse(
            datasets=datasets,
            count=len(datasets)
        )

    except Exception as e:
        logger.error(f"Error listing datasets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list datasets: {str(e)}"
        )


# ============================================================================
# Dataset Query Endpoint
# ============================================================================

@router.post(
    "/datasets/{dataset_id}",
    response_model=DatasetResponse,
    tags=["Datasets"],
    summary="Query a dataset",
    description="Fetch data from a specific dataset with filters"
)
async def query_dataset(
    dataset_id: str = Path(
        ...,
        description="Dataset ID (e.g., 'player_game', 'schedule', 'pbp')",
        examples=["player_game", "schedule", "play_by_play"]
    ),
    request: DatasetRequest = DatasetRequest()
) -> DatasetResponse:
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
        logger.info(
            f"Dataset query: {dataset_id} with filters {request.filters}"
        )

        # Call existing get_dataset() function - NO CHANGES NEEDED!
        df = get_dataset(
            grouping=dataset_id,
            filters=request.filters,
            columns=None,  # Return all columns
            limit=request.limit,
            as_format="pandas",  # We'll convert to requested format
            name_resolver=None,  # Use default name resolution
            force_fresh=False  # Use cache when available
        )

        # Handle pagination with offset
        if request.offset and request.offset > 0:
            df = df.iloc[request.offset:]

        # Convert DataFrame to response format
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
                timestamp=datetime.utcnow()
            )

        logger.info(
            f"Dataset query completed: {dataset_id}, "
            f"{metadata.row_count if metadata else 0} rows, "
            f"{execution_time:.2f}ms"
        )

        return DatasetResponse(
            data=data,
            columns=columns,
            metadata=metadata
        )

    except KeyError as e:
        # Dataset not found
        logger.warning(f"Dataset not found: {dataset_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except ValueError as e:
        # Invalid filters
        logger.warning(f"Invalid filters for {dataset_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        # Unexpected error
        logger.error(
            f"Error querying dataset {dataset_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query dataset: {str(e)}"
        )


# ============================================================================
# Recent Games Convenience Endpoint
# ============================================================================

@router.get(
    "/recent-games/{league}",
    response_model=DatasetResponse,
    tags=["Convenience"],
    summary="Get recent games",
    description="Convenience endpoint for fetching recent games without date filters"
)
async def get_recent_games_endpoint(
    league: str = Path(
        ...,
        description="League identifier",
        examples=["NCAA-MBB", "NCAA-WBB", "EuroLeague"]
    ),
    days: int = Query(
        default=2,
        description="Number of days to look back (1 = today only)",
        ge=1,
        le=30
    ),
    teams: str = Query(
        default=None,
        description="Comma-separated list of team names (optional)"
    ),
    division: str = Query(
        default=None,
        description="Division filter for NCAA (D1, D2, D3, all)"
    ),
    output_format: str = Query(
        default="json",
        description="Output format (json, csv, parquet, records)",
        pattern="^(json|csv|parquet|records)$"
    )
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
            league=league,
            days=days,
            teams=teams_list,
            Division=division,
            force_fresh=False
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
                "division": division
            },
            row_count=len(data) if isinstance(data, list) else 0,
            total_rows=len(df) if df is not None else 0,
            execution_time_ms=round(execution_time, 2),
            cached=execution_time < 100,
            timestamp=datetime.utcnow()
        )

        return DatasetResponse(
            data=data,
            columns=columns,
            metadata=metadata
        )

    except Exception as e:
        logger.error(
            f"Error fetching recent games for {league}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent games: {str(e)}"
        )


# ============================================================================
# Dataset Info Endpoint
# ============================================================================

@router.get(
    "/datasets/{dataset_id}/info",
    response_model=DatasetInfo,
    tags=["Datasets"],
    summary="Get dataset info",
    description="Get metadata about a specific dataset"
)
async def get_dataset_info(
    dataset_id: str = Path(
        ...,
        description="Dataset ID",
        examples=["player_game", "schedule"]
    )
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
        dataset = next(
            (ds for ds in datasets_raw if ds["id"] == dataset_id),
            None
        )

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found"
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
            sample_columns=dataset.get("sample_columns", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset info: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dataset info: {str(e)}"
        )
