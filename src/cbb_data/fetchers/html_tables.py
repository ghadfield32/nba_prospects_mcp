"""Shared HTML Table Parsing Utilities

Reusable helpers for scraping HTML tables from league websites using pandas.read_html().
Provides retry logic, table selection, and error handling.

This module consolidates common HTML scraping patterns used across multiple fetchers:
- NBL (Australia)
- ACB (Spain)
- LNB Pro A (France)
- ABA League (Adriatic)
- BAL (Basketball Africa League)
- BCL (Basketball Champions League)
- LKL (Lithuania)
- BBL, BSL, LBA (Germany, Turkey, Italy)

Key Features:
- Retry logic with exponential backoff
- Intelligent table selection (finds first suitable table)
- Rate limiting integration
- UTF-8 encoding support for international names
- Clear error messages

Usage:
    from .html_tables import read_first_table

    df = read_first_table("https://example.com/stats")
    df["league"] = "NBL"
    df["season"] = "2024-25"
"""

from __future__ import annotations

import logging
import random
import time
from io import StringIO
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def read_first_table(
    url: str,
    min_columns: int = 3,
    min_rows: int = 1,
    timeout: int = 30,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Read the first suitable table from an HTML page

    Tries to find the first non-empty table with at least `min_columns` columns
    and `min_rows` rows. Includes retry logic with exponential backoff.

    Args:
        url: URL to fetch HTML from
        min_columns: Minimum number of columns required (default: 3)
        min_rows: Minimum number of rows required (default: 1)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
        headers: Optional custom HTTP headers

    Returns:
        First suitable DataFrame from the page

    Raises:
        RuntimeError: If no suitable table found after all retries
        requests.HTTPError: If HTTP request fails

    Example:
        >>> df = read_first_table("https://nbl.com.au/stats/players")
        >>> print(f"Found table with {len(df)} rows, {len(df.columns)} columns")
    """
    # Default headers for web scraping
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    last_error = None

    for attempt in range(max_retries):
        try:
            # Fetch HTML content
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            # Parse HTML tables with pandas (use StringIO to avoid FutureWarning)
            tables = pd.read_html(StringIO(response.text), encoding="utf-8")

            # Find first suitable table
            for i, table in enumerate(tables):
                if table.shape[1] >= min_columns and len(table) >= min_rows:
                    logger.debug(
                        f"Selected table {i} from {url}: "
                        f"{len(table)} rows × {table.shape[1]} columns"
                    )
                    return table

            # No suitable table found
            raise ValueError(
                f"No suitable table found at {url}. "
                f"Found {len(tables)} tables but none met criteria "
                f"(min_columns={min_columns}, min_rows={min_rows})"
            )

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                wait_time = (2**attempt) * 1.5 + random.random()
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed for {url}: {e}")

    # All retries exhausted
    raise RuntimeError(
        f"Failed to fetch table from {url} after {max_retries} attempts. Last error: {last_error}"
    )


def read_all_tables(
    url: str,
    timeout: int = 30,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
) -> list[pd.DataFrame]:
    """Read all tables from an HTML page

    Returns all tables found on the page. Useful when you need to inspect
    multiple tables or select a specific one by index.

    Args:
        url: URL to fetch HTML from
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
        headers: Optional custom HTTP headers

    Returns:
        List of DataFrames (one per table found)

    Raises:
        RuntimeError: If request fails after all retries
        requests.HTTPError: If HTTP request fails

    Example:
        >>> tables = read_all_tables("https://acb.com/estadisticas")
        >>> players_df = tables[0]  # First table is usually players
        >>> teams_df = tables[1]    # Second table is usually teams
    """
    # Default headers
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    last_error = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            tables: list[Any] = pd.read_html(StringIO(response.text), encoding="utf-8")
            logger.debug(f"Found {len(tables)} tables at {url}")
            return tables

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (2**attempt) * 1.5 + random.random()
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)

    raise RuntimeError(
        f"Failed to fetch tables from {url} after {max_retries} attempts. Last error: {last_error}"
    )


def normalize_league_columns(
    df: pd.DataFrame,
    league: str,
    season: str,
    competition: str,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Normalize DataFrame columns to standard schema

    Adds league metadata columns and renames sport-specific columns to
    standard names (e.g., "Puntos" → "PTS" for Spanish leagues).

    Args:
        df: Input DataFrame
        league: League code (e.g., "NBL", "ACB", "LNB")
        season: Season string (e.g., "2024-25")
        competition: Competition name (e.g., "Liga Endesa", "NBL")
        column_map: Optional dictionary mapping source → standard column names

    Returns:
        DataFrame with normalized columns

    Example:
        >>> # Spanish ACB league
        >>> column_map = {"Jugador": "PLAYER_NAME", "Puntos": "PTS"}
        >>> df = normalize_league_columns(df, "ACB", "2024-25", "Liga Endesa", column_map)
    """
    df = df.copy()

    # Add league metadata
    df["LEAGUE"] = league
    df["SEASON"] = season
    df["COMPETITION"] = competition

    # Apply column mapping if provided
    if column_map:
        df = df.rename(columns=column_map)

    # Ensure UTF-8 encoding for player/team names
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = df[col].astype(str).str.normalize("NFKC")
            except Exception:
                pass

    return df
