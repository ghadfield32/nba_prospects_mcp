"""
Data saving utilities for basketball datasets.

Provides functions to save DataFrames in various formats:
- CSV: Human-readable, widely compatible
- Parquet: Compressed columnar format, fast reads
- JSON: Standard web format
- DuckDB: SQL database for querying

Usage:
    from cbb_data.storage.save_data import save_to_disk

    # Save as Parquet (recommended)
    save_to_disk(df, 'output/schedule_2024.parquet', format='parquet')

    # Save as CSV
    save_to_disk(df, 'output/schedule_2024.csv', format='csv')

    # Auto-detect format from extension
    save_to_disk(df, 'output/schedule_2024.parquet')  # automatically uses Parquet
"""

import logging
from pathlib import Path
from typing import Any, Literal

import pandas as pd

logger = logging.getLogger(__name__)

# Type alias for supported formats
FormatType = Literal["csv", "parquet", "json", "duckdb"]


def save_to_disk(
    df: pd.DataFrame,
    output_path: str | Path,
    format: FormatType | None = None,
    compression: str = "zstd",
    **kwargs: Any,
) -> None:
    """
    Save DataFrame to disk in various formats.

    Auto-detects format from file extension if not specified.

    Formats:
    - CSV (.csv): Human-readable, widely compatible
      - Good for: Small datasets, sharing with non-technical users
      - Size: ~100-200 MB for 1M rows
      - Speed: Slow reads/writes

    - Parquet (.parquet): Compressed columnar format (recommended)
      - Good for: Large datasets, fast analytics, long-term storage
      - Size: ~20-50 MB for 1M rows (5-10x smaller than CSV)
      - Speed: Very fast reads, moderate writes
      - Default compression: ZSTD (best balance of speed/size)

    - JSON (.json): Standard web format
      - Good for: APIs, web applications
      - Size: ~150-300 MB for 1M rows
      - Speed: Slow reads/writes

    - DuckDB (.duckdb): SQL database
      - Good for: Complex queries, multi-dataset projects
      - Size: ~30-60 MB for 1M rows
      - Speed: Very fast reads with SQL

    Args:
        df: DataFrame to save
        output_path: Output file path (with extension)
        format: File format (auto-detected from extension if None)
        compression: Compression algorithm for Parquet/CSV
                     Options: 'zstd' (default), 'gzip', 'snappy', None
        **kwargs: Additional format-specific arguments

    Raises:
        ValueError: If format is unsupported or cannot be auto-detected
        IOError: If write operation fails

    Examples:
        >>> # Recommended: Save as Parquet
        >>> save_to_disk(df, 'data/schedule_2024.parquet')

        >>> # Save as CSV with gzip compression
        >>> save_to_disk(df, 'data/schedule_2024.csv.gz', compression='gzip')

        >>> # Save as JSON (pretty-printed)
        >>> save_to_disk(df, 'data/schedule_2024.json', orient='records', indent=2)

        >>> # Save to DuckDB table
        >>> save_to_disk(df, 'data/basketball.duckdb', format='duckdb', table='schedule_2024')
    """

    if df.empty:
        logger.warning("DataFrame is empty - nothing to save")
        return

    # Convert to Path object for consistent handling
    path: Path = Path(output_path)

    # Auto-detect format from extension if not specified
    if format is None:
        format = _detect_format(path)

    # Create parent directories if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    # Save based on format
    try:
        if format == "csv":
            _save_csv(df, path, compression, **kwargs)

        elif format == "parquet":
            _save_parquet(df, path, compression, **kwargs)

        elif format == "json":
            _save_json(df, path, **kwargs)

        elif format == "duckdb":
            _save_duckdb(df, path, **kwargs)

        else:
            raise ValueError(f"Unsupported format: {format}")

        # Log success with file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        logger.info(
            f"✓ Saved {len(df):,} rows to {path.name} " f"({file_size_mb:.2f} MB, {format})"
        )

    except Exception as e:
        logger.error(f"Failed to save DataFrame: {e}")
        raise OSError(f"Failed to write {path}: {e}") from e


def _detect_format(path: Path) -> FormatType:
    """Auto-detect format from file extension."""

    suffix = path.suffix.lower()

    # Handle double extensions like .csv.gz
    if path.suffixes:
        suffixes = [s.lower() for s in path.suffixes]
        if ".csv" in suffixes:
            return "csv"
        elif ".json" in suffixes:
            return "json"

    # Single extension detection
    format_map = {
        ".csv": "csv",
        ".parquet": "parquet",
        ".pq": "parquet",
        ".json": "json",
        ".jsonl": "json",
        ".duckdb": "duckdb",
        ".db": "duckdb",
    }

    detected = format_map.get(suffix)

    if detected is None:
        raise ValueError(
            f"Cannot auto-detect format from extension '{suffix}'. "
            f"Supported extensions: {list(format_map.keys())}"
        )

    # Type is guaranteed to be FormatType after None check
    return detected  # type: ignore[return-value]


def _save_csv(df: pd.DataFrame, path: Path, compression: str, **kwargs: Any) -> None:
    """Save DataFrame as CSV."""

    # Default CSV options
    default_args = {
        "index": False,
        "encoding": "utf-8",
    }

    # Handle compression
    if compression and compression != "None":
        default_args["compression"] = compression

    # Merge with user-provided kwargs
    save_args = {**default_args, **kwargs}

    df.to_csv(path, **save_args)
    logger.debug(f"CSV saved with args: {save_args}")


def _save_parquet(df: pd.DataFrame, path: Path, compression: str, **kwargs: Any) -> None:
    """Save DataFrame as Parquet."""

    # Default Parquet options
    default_args = {
        "index": False,
        "engine": "pyarrow",  # Faster than fastparquet
    }

    # Set compression (ZSTD = best balance of speed/size)
    if compression:
        default_args["compression"] = compression

    # Merge with user-provided kwargs
    save_args = {**default_args, **kwargs}

    df.to_parquet(path, **save_args)
    logger.debug(f"Parquet saved with args: {save_args}")


def _save_json(df: pd.DataFrame, path: Path, **kwargs: Any) -> None:
    """Save DataFrame as JSON."""

    # Default JSON options
    default_args = {
        "orient": "records",  # List of records (most common)
        "lines": False,  # Pretty JSON by default
    }

    # Merge with user-provided kwargs
    save_args = {**default_args, **kwargs}

    # Handle JSONL (newline-delimited JSON)
    if path.suffix == ".jsonl":
        save_args["orient"] = "records"
        save_args["lines"] = True

    df.to_json(path, **save_args)
    logger.debug(f"JSON saved with args: {save_args}")


def _save_duckdb(df: pd.DataFrame, path: Path, **kwargs: Any) -> None:
    """Save DataFrame to DuckDB table."""

    try:
        import duckdb
    except ImportError:
        raise ImportError(
            "DuckDB is required for this feature. Install it with: pip install duckdb"
        ) from None

    # Get table name from kwargs or use filename
    table_name = kwargs.pop("table", path.stem)

    # Connect to DuckDB (creates file if doesn't exist)
    conn = duckdb.connect(str(path))

    try:
        # Create or replace table
        conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
        logger.debug(f"DuckDB table '{table_name}' created in {path.name}")

    finally:
        conn.close()


def get_recommended_format(row_count: int, use_case: str = "general") -> FormatType:
    """
    Get recommended file format based on data size and use case.

    Args:
        row_count: Number of rows in DataFrame
        use_case: Intended use case
                  - 'general': Default recommendation
                  - 'sharing': For sharing with non-technical users
                  - 'analytics': For data analysis workflows
                  - 'web': For web applications/APIs

    Returns:
        Recommended format

    Examples:
        >>> get_recommended_format(1000, 'sharing')
        'csv'
        >>> get_recommended_format(1_000_000, 'analytics')
        'parquet'
    """

    if use_case == "web":
        return "json"

    if use_case == "sharing":
        # CSV is more widely understood
        return "csv" if row_count < 100_000 else "parquet"

    if use_case == "analytics":
        # Parquet or DuckDB for analytics
        return "parquet" if row_count < 10_000_000 else "duckdb"

    # General recommendation: Parquet for larger datasets
    if row_count < 10_000:
        return "csv"  # Small enough that format doesn't matter
    elif row_count < 1_000_000:
        return "parquet"  # Good balance
    else:
        return "duckdb"  # Best for very large datasets


def estimate_file_size(row_count: int, column_count: int, format: FormatType) -> float:
    """
    Estimate file size in MB for a given format.

    Very rough estimates based on typical basketball data:
    - Average row: ~500 bytes uncompressed
    - CSV: ~200 bytes/row (text)
    - Parquet: ~40 bytes/row (compressed columnar)
    - JSON: ~300 bytes/row (text with structure)
    - DuckDB: ~50 bytes/row (compressed binary)

    Args:
        row_count: Number of rows
        column_count: Number of columns
        format: File format

    Returns:
        Estimated file size in MB
    """

    # Bytes per row (rough estimates)
    bytes_per_row = {
        "csv": 200,
        "parquet": 40,
        "json": 300,
        "duckdb": 50,
    }

    base_bytes = bytes_per_row.get(format, 100)

    # Adjust for column count (more columns = more data)
    adjusted_bytes = base_bytes * (column_count / 10)  # Assume 10 columns baseline

    # Calculate size in MB
    total_bytes = row_count * adjusted_bytes
    size_mb = total_bytes / (1024 * 1024)

    return round(size_mb, 2)
