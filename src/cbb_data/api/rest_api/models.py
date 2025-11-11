"""
Pydantic models for REST API request/response schemas.

These models provide validation, serialization, and OpenAPI documentation
for all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DatasetRequest(BaseModel):
    """
    Request body for querying a dataset.

    This model wraps the filter parameters that are passed to get_dataset().
    All validation is delegated to the existing FilterSpec class.
    """

    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filter parameters (league, season, team, player, date, etc.)",
        examples=[
            {"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]},
            {"league": "EuroLeague", "season": "2024", "player": ["Luka Doncic"]},
        ],
    )

    limit: int | None = Field(
        default=None, description="Maximum number of rows to return", ge=1, le=10000
    )

    offset: int | None = Field(
        default=0, description="Number of rows to skip (for pagination)", ge=0
    )

    output_format: Literal["json", "csv", "parquet", "records", "ndjson"] = Field(
        default="json",
        description="Output format: 'json' (array of arrays), 'csv' (comma-separated), 'parquet' (compressed binary), 'records' (array of objects), 'ndjson' (streaming newline-delimited JSON)",
    )

    include_metadata: bool = Field(
        default=True, description="Include metadata about the query execution"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "filters": {"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]},
                "limit": 50,
                "offset": 0,
                "output_format": "json",
                "include_metadata": True,
            }
        }


class DatasetMetadata(BaseModel):
    """Metadata about the dataset query execution."""

    dataset_id: str = Field(description="ID of the dataset queried")
    filters_applied: dict[str, Any] = Field(description="Filters that were applied")
    row_count: int = Field(description="Number of rows returned")
    total_rows: int | None = Field(default=None, description="Total rows available (if known)")
    execution_time_ms: float = Field(description="Query execution time in milliseconds")
    cached: bool = Field(description="Whether result was served from cache")
    cache_key: str | None = Field(default=None, description="Cache key used")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of query execution (UTC)"
    )


class DatasetResponse(BaseModel):
    """
    Response from a dataset query.

    Contains the data rows and optional metadata about the query.
    """

    data: list[Any] | str | bytes = Field(
        description="Dataset rows: List for json/records format, str for csv format, bytes for parquet format"
    )

    columns: list[str] | None = Field(
        default=None, description="Column names (included when output_format='json' or 'csv')"
    )

    metadata: DatasetMetadata | None = Field(default=None, description="Query execution metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    ["Cooper Flagg", "2025-01-15", 25, 8, 6],
                    ["RJ Davis", "2025-01-15", 22, 5, 4],
                ],
                "columns": ["PLAYER_NAME", "GAME_DATE", "PTS", "REB", "AST"],
                "metadata": {
                    "dataset_id": "player_game",
                    "filters_applied": {"league": "NCAA-MBB", "team": ["Duke"]},
                    "row_count": 2,
                    "execution_time_ms": 45.3,
                    "cached": True,
                    "timestamp": "2025-01-15T12:00:00Z",
                },
            }
        }


class DatasetInfo(BaseModel):
    """Information about a single dataset."""

    id: str = Field(description="Dataset unique identifier")
    name: str = Field(description="Human-readable dataset name")
    description: str = Field(description="Dataset description")
    keys: list[str] = Field(description="Primary key columns")
    supported_filters: list[str] = Field(description="Filters this dataset supports")
    supported_leagues: list[str] = Field(description="Leagues this dataset covers")
    data_sources: list[str] = Field(description="Underlying data sources")
    sample_columns: list[str] = Field(description="Example columns in the dataset")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "player_game",
                "name": "Player Game Stats",
                "description": "Per-player per-game box score statistics",
                "keys": ["PLAYER_ID", "GAME_ID"],
                "supported_filters": ["league", "season", "team", "player", "date", "game_ids"],
                "supported_leagues": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                "data_sources": ["ESPN", "CBBpy", "EuroLeague API"],
                "sample_columns": ["PLAYER_NAME", "PTS", "REB", "AST", "MIN", "FG_PCT"],
            }
        }


class DatasetsListResponse(BaseModel):
    """Response for listing all available datasets."""

    datasets: list[DatasetInfo] = Field(description="List of all available datasets")
    count: int = Field(description="Total number of datasets")

    class Config:
        json_schema_extra = {
            "example": {
                "datasets": [
                    {
                        "id": "schedule",
                        "name": "Game Schedule",
                        "description": "Game schedules and results",
                        "keys": ["GAME_ID"],
                        "supported_filters": ["league", "season", "team", "date"],
                        "supported_leagues": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                        "data_sources": ["ESPN", "EuroLeague API"],
                        "sample_columns": ["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE"],
                    }
                ],
                "count": 8,
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Overall service health status"
    )
    version: str = Field(description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Current server time (UTC)"
    )
    services: dict[str, str] = Field(
        default_factory=dict, description="Status of individual service components"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2025-01-15T12:00:00Z",
                "services": {"database": "healthy", "cache": "healthy", "data_sources": "healthy"},
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    detail: dict[str, Any] | None = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of error (UTC)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid filter parameters provided",
                "detail": {
                    "field": "season",
                    "value": "2030",
                    "reason": "Season must be between 2002 and 2025",
                },
                "timestamp": "2025-01-15T12:00:00Z",
            }
        }


class RecentGamesRequest(BaseModel):
    """Request for recent games endpoint."""

    days: int = Field(
        default=1, description="Number of days to look back (1 = today only)", ge=1, le=30
    )

    include_scores: bool = Field(
        default=True, description="Include final scores for completed games"
    )

    class Config:
        json_schema_extra = {"example": {"days": 2, "include_scores": True}}
