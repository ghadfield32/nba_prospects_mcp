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


# ============================================================================
# LNB-specific models for data readiness and validation
# ============================================================================


class LNBSeasonReadiness(BaseModel):
    """Readiness status for a single LNB season."""

    season: str = Field(description="Season identifier (e.g., '2023-2024')")
    ready_for_modeling: bool = Field(
        description="Whether season meets criteria for modeling (≥95% coverage, 0 errors)"
    )
    pbp_coverage: int = Field(description="Number of PBP files on disk")
    pbp_expected: int = Field(description="Expected number of PBP files")
    pbp_pct: float = Field(description="PBP coverage percentage")
    shots_coverage: int = Field(description="Number of shots files on disk")
    shots_expected: int = Field(description="Expected number of shots files")
    shots_pct: float = Field(description="Shots coverage percentage")
    num_critical_issues: int = Field(description="Number of critical errors found")

    class Config:
        json_schema_extra = {
            "example": {
                "season": "2023-2024",
                "ready_for_modeling": True,
                "pbp_coverage": 306,
                "pbp_expected": 306,
                "pbp_pct": 100.0,
                "shots_coverage": 306,
                "shots_expected": 306,
                "shots_pct": 100.0,
                "num_critical_issues": 0,
            }
        }


class LNBReadinessResponse(BaseModel):
    """Response for LNB season readiness check."""

    checked_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of readiness check (UTC)"
    )
    seasons: list[LNBSeasonReadiness] = Field(description="Readiness status per season")
    any_season_ready: bool = Field(description="Whether at least one season is ready for modeling")
    ready_seasons: list[str] = Field(description="List of seasons ready for modeling")

    class Config:
        json_schema_extra = {
            "example": {
                "checked_at": "2025-11-16T12:00:00Z",
                "seasons": [
                    {
                        "season": "2023-2024",
                        "ready_for_modeling": True,
                        "pbp_coverage": 306,
                        "pbp_expected": 306,
                        "pbp_pct": 100.0,
                        "shots_coverage": 306,
                        "shots_expected": 306,
                        "shots_pct": 100.0,
                        "num_critical_issues": 0,
                    }
                ],
                "any_season_ready": True,
                "ready_seasons": ["2023-2024"],
            }
        }


class LNBValidationStatusResponse(BaseModel):
    """Response for LNB validation status check."""

    run_at: datetime = Field(description="Timestamp of last validation run (UTC)")
    golden_fixtures_passed: bool = Field(
        description="Whether golden fixtures regression testing passed"
    )
    golden_failures: int = Field(description="Number of golden fixture failures")
    api_spotcheck_passed: bool = Field(
        description="Whether API spot-check passed (sampled games match)"
    )
    api_discrepancies: int = Field(description="Number of API discrepancies found")
    consistency_errors: int = Field(description="Number of per-game consistency errors")
    consistency_warnings: int = Field(description="Number of per-game consistency warnings")
    ready_for_live: bool = Field(description="Whether system is ready for live game ingestion")
    seasons: list[LNBSeasonReadiness] = Field(description="Readiness status per season")

    class Config:
        json_schema_extra = {
            "example": {
                "run_at": "2025-11-16T12:00:00Z",
                "golden_fixtures_passed": True,
                "golden_failures": 0,
                "api_spotcheck_passed": True,
                "api_discrepancies": 0,
                "consistency_errors": 0,
                "consistency_warnings": 2,
                "ready_for_live": True,
                "seasons": [
                    {
                        "season": "2023-2024",
                        "ready_for_modeling": True,
                        "pbp_coverage": 306,
                        "pbp_expected": 306,
                        "pbp_pct": 100.0,
                        "shots_coverage": 306,
                        "shots_expected": 306,
                        "shots_pct": 100.0,
                        "num_critical_issues": 0,
                    }
                ],
            }
        }


class LNBErrorResponse(BaseModel):
    """Standardized error response for LNB endpoints."""

    error_code: Literal[
        "SEASON_NOT_READY",
        "INVALID_SEASON",
        "GAME_NOT_FOUND",
        "VALIDATION_FAILED",
        "INTERNAL_ERROR",
    ] = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    season: str | None = Field(default=None, description="Season related to error (if applicable)")
    detail: dict[str, Any] | None = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of error (UTC)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "SEASON_NOT_READY",
                "message": "Season 2024-2025 is NOT READY for modeling (Coverage: 45.2%/42.8%, Errors: 3)",
                "season": "2024-2025",
                "detail": {
                    "pbp_coverage": 45.2,
                    "shots_coverage": 42.8,
                    "num_critical_issues": 3,
                },
                "timestamp": "2025-11-16T12:00:00Z",
            }
        }
