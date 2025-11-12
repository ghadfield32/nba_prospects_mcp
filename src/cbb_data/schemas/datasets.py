"""Schema definitions for datasets"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetInfo(BaseModel):
    """Metadata about a dataset

    Each dataset in the catalog provides this metadata to help users
    understand what data is available and how to filter it.
    """

    id: str = Field(description="Unique dataset identifier (e.g., 'player_game')")

    keys: list[str] = Field(
        description="Primary key columns for this dataset (e.g., ['PLAYER_ID', 'GAME_ID'])"
    )

    filters: list[str] = Field(
        description="List of filter types supported (e.g., ['season', 'team', 'player'])"
    )

    description: str = Field(description="Human-readable description of the dataset")

    sources: list[str] = Field(
        default=[], description="Data sources used (e.g., ['ESPN', 'EuroLeague API'])"
    )

    leagues: list[str] = Field(
        default=[], description="Supported leagues (e.g., ['NCAA-MBB', 'NCAA-WBB', 'EuroLeague'])"
    )

    sample_columns: list[str] = Field(
        default=[], description="Sample of available columns in the dataset"
    )

    requires_game_id: bool = Field(
        default=False, description="Whether this dataset requires specific game_ids (e.g., PBP)"
    )

    levels: list[str] = Field(
        default=[],
        description="Competition levels included (e.g., ['college', 'prepro']). Empty = all levels.",
    )


class DatasetMetrics(BaseModel):
    """Performance metrics for dataset fetches"""

    dataset_id: str
    fetch_time_seconds: float
    rows_returned: int
    cache_hit: bool
    source: str
