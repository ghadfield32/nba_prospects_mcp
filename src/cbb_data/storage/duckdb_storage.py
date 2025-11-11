"""
DuckDB-based persistent storage layer for basketball data.

Provides fast, SQL-queryable local storage with automatic table management.
Uses DuckDB for optimal performance on analytical queries (30-600x faster than pandas).

Features:
- Persistent storage across sessions (survives memory cache TTL)
- SQL-based filtering and aggregation
- Automatic table naming: {dataset}_{league}_{season}
- Multi-season queries with UNION ALL (fast merging)
- Parquet export with compression

Usage:
    from cbb_data.storage.duckdb_storage import get_storage

    storage = get_storage()

    # Save data
    storage.save(df, dataset='schedule', league='NCAA-MBB', season='2024')

    # Load data
    df = storage.load(dataset='schedule', league='NCAA-MBB', season='2024')

    # Load multiple seasons (fast SQL UNION ALL)
    df = storage.load_multi_season(
        dataset='schedule',
        league='NCAA-MBB',
        seasons=['2024', '2023', '2022']
    )
"""

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

# Global storage instance (singleton pattern)
_storage_instance: Optional["DuckDBStorage"] = None


class DuckDBStorage:
    """
    DuckDB-based persistent storage for basketball data.

    Provides fast SQL-queryable storage with automatic table management.
    """

    def __init__(self, db_path: str = "data/basketball.duckdb"):
        """
        Initialize DuckDB storage.

        Args:
            db_path: Path to DuckDB database file (created if doesn't exist)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize connection (file-based for persistence)
        self.conn = duckdb.connect(str(self.db_path))

        logger.info(f"DuckDB storage initialized at {self.db_path}")

    def _get_table_name(self, dataset: str, league: str, season: str) -> str:
        """
        Generate standardized table name.

        Format: {dataset}_{league}_{season}
        Example: schedule_NCAA_MBB_2024
        """
        # Sanitize league name (replace hyphens with underscores)
        league_clean = league.replace("-", "_")
        return f"{dataset}_{league_clean}_{season}"

    def save(self, df: pd.DataFrame, dataset: str, league: str, season: str) -> None:
        """
        Save DataFrame to DuckDB table.

        Creates or replaces table with standardized naming.

        Args:
            df: DataFrame to save
            dataset: Dataset name ('schedule', 'player_game', etc.)
            league: League code ('NCAA-MBB', 'EuroLeague')
            season: Season string ('2024', '2023', etc.)

        Example:
            >>> storage.save(df, 'schedule', 'NCAA-MBB', '2024')
            # Creates table: schedule_NCAA_MBB_2024
        """
        if df.empty:
            logger.warning(f"Empty DataFrame - skipping save for {dataset}/{league}/{season}")
            return

        table_name = self._get_table_name(dataset, league, season)

        try:
            # Create or replace table from DataFrame
            self.conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")

            row_count = len(df)
            logger.debug(f"Saved {row_count:,} rows to table: {table_name}")

        except Exception as e:
            logger.error(f"Failed to save to DuckDB: {e}")
            raise

    def load(
        self,
        dataset: str,
        league: str,
        season: str,
        filter_sql: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Load data from DuckDB table.

        Args:
            dataset: Dataset name
            league: League code
            season: Season string
            filter_sql: Optional SQL WHERE clause (e.g., "TEAM_NAME = 'Duke'")
            limit: Optional row limit

        Returns:
            pd.DataFrame: Loaded data

        Example:
            >>> df = storage.load('schedule', 'NCAA-MBB', '2024', limit=100)
            >>> df = storage.load('schedule', 'NCAA-MBB', '2024', filter_sql="HOME_TEAM = 'Duke'")
        """
        table_name = self._get_table_name(dataset, league, season)

        # Check if table exists
        if not self.has_data(dataset, league, season):
            logger.warning(f"Table not found: {table_name}")
            return pd.DataFrame()

        # Build query
        query = f"SELECT * FROM {table_name}"

        if filter_sql:
            query += f" WHERE {filter_sql}"

        if limit:
            query += f" LIMIT {limit}"

        try:
            df = self.conn.execute(query).df()
            logger.debug(f"Loaded {len(df):,} rows from {table_name}")
            return df

        except Exception as e:
            logger.error(f"Failed to load from DuckDB: {e}")
            return pd.DataFrame()

    def load_multi_season(
        self,
        dataset: str,
        league: str,
        seasons: list[str],
        filter_sql: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Load data from multiple seasons using SQL UNION ALL.

        This is 30-600x faster than pandas concat for large datasets.

        Args:
            dataset: Dataset name
            league: League code
            seasons: List of season strings
            filter_sql: Optional SQL WHERE clause applied to each table
            limit: Optional row limit for final result

        Returns:
            pd.DataFrame: Combined data from all seasons

        Example:
            >>> df = storage.load_multi_season(
            ...     'schedule',
            ...     'NCAA-MBB',
            ...     ['2024', '2023', '2022'],
            ...     limit=1000
            ... )
        """
        if not seasons:
            return pd.DataFrame()

        # Get table names for existing seasons
        available_tables = []
        for season in seasons:
            if self.has_data(dataset, league, season):
                table_name = self._get_table_name(dataset, league, season)
                available_tables.append(table_name)

        if not available_tables:
            logger.warning(f"No tables found for {dataset}/{league} in seasons: {seasons}")
            return pd.DataFrame()

        # Build UNION ALL query
        queries = []
        for table_name in available_tables:
            query = f"SELECT * FROM {table_name}"
            if filter_sql:
                query += f" WHERE {filter_sql}"
            queries.append(f"({query})")

        union_query = " UNION ALL ".join(queries)

        if limit:
            union_query = f"SELECT * FROM ({union_query}) LIMIT {limit}"

        try:
            df = self.conn.execute(union_query).df()
            logger.info(
                f"Loaded {len(df):,} rows from {len(available_tables)} seasons using SQL UNION ALL"
            )
            return df

        except Exception as e:
            logger.error(f"Failed to load multi-season from DuckDB: {e}")
            return pd.DataFrame()

    def has_data(self, dataset: str, league: str, season: str) -> bool:
        """
        Check if data exists for given dataset/league/season.

        Args:
            dataset: Dataset name
            league: League code
            season: Season string

        Returns:
            bool: True if table exists, False otherwise
        """
        table_name = self._get_table_name(dataset, league, season)

        try:
            # Query to check if table exists
            result = self.conn.execute(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
            ).fetchone()

            if result is None:
                return False

            exists: bool = bool(result[0] > 0)
            return exists

        except Exception as e:
            logger.debug(f"Error checking table existence: {e}")
            return False

    def export_to_parquet(
        self, dataset: str, league: str, season: str, output_path: str, compression: str = "zstd"
    ) -> None:
        """
        Export DuckDB table to Parquet file.

        Args:
            dataset: Dataset name
            league: League code
            season: Season string
            output_path: Output Parquet file path
            compression: Compression algorithm ('zstd', 'gzip', 'snappy')

        Example:
            >>> storage.export_to_parquet(
            ...     'schedule', 'NCAA-MBB', '2024',
            ...     'output/schedule_2024.parquet'
            ... )
        """
        table_name = self._get_table_name(dataset, league, season)

        if not self.has_data(dataset, league, season):
            logger.error(f"Table not found: {table_name}")
            return

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # DuckDB can export directly to Parquet (very fast)
            query = f"COPY {table_name} TO '{output_file}' (FORMAT PARQUET, COMPRESSION {compression.upper()})"
            self.conn.execute(query)

            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            logger.info(f"Exported {table_name} to {output_file.name} ({file_size_mb:.2f} MB)")

        except Exception as e:
            logger.error(f"Failed to export to Parquet: {e}")
            raise

    def list_tables(self) -> list[str]:
        """
        List all tables in the database.

        Returns:
            List[str]: Table names
        """
        try:
            result = self.conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()

            tables = [row[0] for row in result]
            return tables

        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []

    def close(self) -> None:
        """Close DuckDB connection."""
        if hasattr(self, "conn"):
            self.conn.close()
            logger.debug("DuckDB connection closed")


def get_storage(db_path: str = "data/basketball.duckdb") -> DuckDBStorage:
    """
    Get or create global DuckDB storage instance (singleton pattern).

    Args:
        db_path: Path to DuckDB database file

    Returns:
        DuckDBStorage: Global storage instance

    Example:
        >>> storage = get_storage()
        >>> storage.save(df, 'schedule', 'NCAA-MBB', '2024')
    """
    global _storage_instance

    if _storage_instance is None:
        _storage_instance = DuckDBStorage(db_path)

    return _storage_instance
