"""Dataset registry

The registry is the central catalog of all available datasets.
Each dataset registers:
- ID (unique identifier)
- Keys (primary key columns)
- Filters (supported filter types)
- Fetch function (how to get the data)
- Compose function (optional enrichment/joining)
- Metadata (description, sources, leagues)
"""

from __future__ import annotations
from typing import Callable, Dict, List, Optional
import pandas as pd
from ..schemas.datasets import DatasetInfo


class DatasetRegistry:
    """Central registry for all basketball datasets

    Usage:
        # Register a dataset
        DatasetRegistry.register(
            id="player_game",
            keys=["PLAYER_ID", "GAME_ID"],
            filters=["season", "team", "player", "date"],
            fetch=fetch_player_game_fn,
            description="Per-player per-game logs"
        )

        # List all datasets
        datasets = DatasetRegistry.list_infos()

        # Get a specific dataset
        entry = DatasetRegistry.get("player_game")
        df = entry["fetch"](params, post_mask)
    """

    _items: Dict[str, Dict] = {}

    @classmethod
    def register(
        cls,
        id: str,
        *,
        keys: List[str],
        filters: List[str],
        fetch: Callable[[Dict, Dict], pd.DataFrame],
        compose: Optional[Callable] = None,
        description: str = "",
        sources: Optional[List[str]] = None,
        leagues: Optional[List[str]] = None,
        sample_columns: Optional[List[str]] = None,
        requires_game_id: bool = False,
    ):
        """Register a dataset in the catalog

        Args:
            id: Unique dataset identifier
            keys: Primary key columns
            filters: List of supported filter names (from FilterSpec)
            fetch: Function that takes (params, post_mask) and returns DataFrame
            compose: Optional function to enrich/compose the data
            description: Human-readable description
            sources: List of data sources (e.g., ["ESPN", "EuroLeague"])
            leagues: List of supported leagues
            sample_columns: Sample column names
            requires_game_id: Whether game_id filter is required
        """
        cls._items[id] = {
            "id": id,
            "keys": keys,
            "filters": filters,  # Renamed from "supports" for API consistency
            "fetch": fetch,
            "compose": compose,
            "description": description,
            "sources": sources or [],
            "leagues": leagues or [],
            "sample_columns": sample_columns or [],
            "requires_game_id": requires_game_id,
        }

    @classmethod
    def get(cls, id: str) -> Dict:
        """Get a registered dataset by ID

        Args:
            id: Dataset identifier

        Returns:
            Dataset entry dictionary

        Raises:
            KeyError: If dataset not found
        """
        if id not in cls._items:
            available = ", ".join(cls._items.keys())
            raise KeyError(
                f"Dataset '{id}' not found. Available datasets: {available}"
            )
        return cls._items[id]

    @classmethod
    def list_ids(cls) -> List[str]:
        """List all registered dataset IDs"""
        return list(cls._items.keys())

    @classmethod
    def list_infos(cls) -> List[DatasetInfo]:
        """List metadata for all registered datasets

        Returns:
            List of DatasetInfo objects
        """
        return [
            DatasetInfo(
                id=v["id"],
                keys=v["keys"],
                filters=v["filters"],  # Renamed from "supports" for API consistency
                description=v["description"],
                sources=v["sources"],
                leagues=v["leagues"],
                sample_columns=v["sample_columns"],
                requires_game_id=v["requires_game_id"],
            )
            for v in cls._items.values()
        ]

    @classmethod
    def clear(cls):
        """Clear all registered datasets (useful for testing)"""
        cls._items.clear()

    @classmethod
    def filter_by_league(cls, league: str) -> List[DatasetInfo]:
        """Get datasets that support a specific league

        Args:
            league: League identifier (e.g., "NCAA-MBB")

        Returns:
            List of DatasetInfo for datasets supporting this league
        """
        return [
            info for info in cls.list_infos()
            if not info.leagues or league in info.leagues
        ]

    @classmethod
    def filter_by_source(cls, source: str) -> List[DatasetInfo]:
        """Get datasets from a specific source

        Args:
            source: Source identifier (e.g., "ESPN")

        Returns:
            List of DatasetInfo for datasets from this source
        """
        return [
            info for info in cls.list_infos()
            if source in info.sources
        ]
