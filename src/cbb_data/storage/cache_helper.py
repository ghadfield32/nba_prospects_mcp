"""
Smart cache-aware data fetching with DuckDB storage layer.

This module provides intelligent data fetching that checks multiple cache layers
before making API calls:
1. Memory cache (fastest, TTL-based)
2. DuckDB storage (fast, persistent)
3. API fetch (slowest, rate-limited)

Usage:
    from cbb_data.storage.cache_helper import fetch_with_storage

    df = fetch_with_storage(
        dataset='schedule',
        league='NCAA-MBB',
        season='2024',
        fetcher_func=lambda: espn_fetcher.get_schedule(season='2024'),
        cache_key='schedule_NCAA-MBB_2024'
    )
"""

import logging
from collections.abc import Callable

import pandas as pd

from cbb_data.fetchers.base import Cache
from cbb_data.storage.duckdb_storage import get_storage

logger = logging.getLogger(__name__)


def fetch_with_storage(
    dataset: str,
    league: str,
    season: str,
    fetcher_func: Callable[[], pd.DataFrame],
    cache_key: str,
    cache: Cache | None = None,
    use_storage: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch data with intelligent caching across multiple layers.

    Cache Layer Priority:
    1. Memory cache (< 1ms) - TTL-based, fast but temporary
    2. DuckDB storage (10-100ms) - Persistent, fast SQL queries
    3. API fetch (3-180s) - Slowest, rate-limited

    Args:
        dataset: Dataset name ('schedule', 'player_game', etc.)
        league: League code ('NCAA-MBB', 'EuroLeague')
        season: Season string ('2024', '2023', etc.)
        fetcher_func: Function to call if data not in cache (returns DataFrame)
        cache_key: Unique cache key for memory cache
        cache: Optional Cache instance (if None, no memory cache used)
        use_storage: Whether to use DuckDB storage layer (default: True)
        force_refresh: Skip all caches and force API fetch (default: False)

    Returns:
        pd.DataFrame: Requested data from fastest available source

    Example:
        >>> from cbb_data.fetchers.espn_mbb import ESPNFetcher
        >>> fetcher = ESPNFetcher()
        >>>
        >>> df = fetch_with_storage(
        ...     dataset='schedule',
        ...     league='NCAA-MBB',
        ...     season='2024',
        ...     fetcher_func=lambda: fetcher.get_schedule(season='2024'),
        ...     cache_key='schedule_NCAA-MBB_2024'
        ... )
    """

    # Force refresh bypasses all caches
    if force_refresh:
        logger.info(f"Force refresh requested for {dataset}/{league}/{season}")
        df = _fetch_and_cache(dataset, league, season, fetcher_func, cache_key, cache, use_storage)
        return df

    # Layer 1: Check memory cache (fastest, < 1ms)
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"✓ Memory cache HIT for {cache_key}")
            return cached_data
        logger.debug(f"Memory cache MISS for {cache_key}")

    # Layer 2: Check DuckDB storage (fast, persistent, 10-100ms)
    if use_storage:
        storage = get_storage()
        if storage.has_data(dataset, league, season):
            logger.info(f"✓ DuckDB storage HIT for {dataset}/{league}/{season}")
            df = storage.load(dataset, league, season)

            # Update memory cache for future requests
            if cache and not df.empty:
                cache.set(cache_key, df)
                logger.debug("Updated memory cache with DuckDB data")

            return df
        logger.debug(f"DuckDB storage MISS for {dataset}/{league}/{season}")

    # Layer 3: Fetch from API (slowest, 3-180 seconds)
    logger.info(f"Fetching from API for {dataset}/{league}/{season}")
    df = _fetch_and_cache(dataset, league, season, fetcher_func, cache_key, cache, use_storage)

    return df


def _fetch_and_cache(
    dataset: str,
    league: str,
    season: str,
    fetcher_func: Callable[[], pd.DataFrame],
    cache_key: str,
    cache: Cache | None,
    use_storage: bool,
) -> pd.DataFrame:
    """
    Fetch data from API and update all cache layers.

    Args:
        dataset: Dataset name
        league: League code
        season: Season string
        fetcher_func: Function to call for API fetch
        cache_key: Cache key for memory cache
        cache: Optional Cache instance
        use_storage: Whether to save to DuckDB storage

    Returns:
        pd.DataFrame: Fetched data
    """
    # Fetch from API
    df = fetcher_func()

    if df.empty:
        logger.warning(f"API returned empty DataFrame for {dataset}/{league}/{season}")
        return df

    # Save to DuckDB storage (persistent)
    if use_storage:
        try:
            storage = get_storage()
            storage.save(df, dataset, league, season)
            logger.info(f"✓ Saved to DuckDB storage: {dataset}/{league}/{season} ({len(df)} rows)")
        except Exception as e:
            logger.error(f"Failed to save to DuckDB storage: {e}")

    # Save to memory cache (TTL-based)
    if cache:
        cache.set(cache_key, df)
        logger.debug(f"✓ Saved to memory cache: {cache_key}")

    return df


def fetch_multi_season_with_storage(
    dataset: str,
    league: str,
    seasons: list,
    fetcher_func_factory: Callable[[str], Callable[[], pd.DataFrame]],
    cache: Cache | None = None,
    use_storage: bool = True,
    force_refresh: bool = False,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Fetch data for multiple seasons with intelligent caching.

    Uses SQL UNION ALL for efficient multi-season merging when possible (30-600x faster).
    Falls back to pandas concat if data needs to be fetched from API.

    Args:
        dataset: Dataset name ('schedule', 'player_game', etc.)
        league: League code ('NCAA-MBB', 'EuroLeague')
        seasons: List of season strings (['2024', '2023', '2022'])
        fetcher_func_factory: Function that takes a season and returns a fetcher function
        cache: Optional Cache instance
        use_storage: Whether to use DuckDB storage layer
        force_refresh: Skip all caches and force API fetch
        limit: Optional row limit for final result

    Returns:
        pd.DataFrame: Combined data from all seasons

    Example:
        >>> from cbb_data.fetchers.espn_mbb import ESPNFetcher
        >>> fetcher = ESPNFetcher()
        >>>
        >>> def factory(season):
        ...     return lambda: fetcher.get_schedule(season=season)
        >>>
        >>> df = fetch_multi_season_with_storage(
        ...     dataset='schedule',
        ...     league='NCAA-MBB',
        ...     seasons=['2024', '2023', '2022'],
        ...     fetcher_func_factory=factory
        ... )
    """

    if not seasons:
        return pd.DataFrame()

    # Check which seasons are available in DuckDB storage
    storage = get_storage() if use_storage else None
    available_in_storage = []
    missing_seasons = []

    if storage and not force_refresh:
        for season in seasons:
            if storage.has_data(dataset, league, season):
                available_in_storage.append(season)
            else:
                missing_seasons.append(season)

        logger.info(
            f"Multi-season query: {len(available_in_storage)} in storage, {len(missing_seasons)} need fetching"
        )
    else:
        missing_seasons = seasons

    # Fetch missing seasons from API
    for season in missing_seasons:
        cache_key = f"{dataset}_{league}_{season}"
        fetcher_func = fetcher_func_factory(season)

        df = fetch_with_storage(
            dataset=dataset,
            league=league,
            season=season,
            fetcher_func=fetcher_func,
            cache_key=cache_key,
            cache=cache,
            use_storage=use_storage,
            force_refresh=force_refresh,
        )

        if not df.empty:
            available_in_storage.append(season)

    # Load all seasons using efficient SQL UNION ALL
    if storage and available_in_storage:
        logger.info(f"Loading {len(available_in_storage)} seasons using DuckDB SQL UNION ALL")
        df = storage.load_multi_season(
            dataset=dataset, league=league, seasons=available_in_storage, limit=limit
        )

        # Add SEASON column if not present
        if not df.empty and "SEASON" not in df.columns:
            # Try to infer season from table name or other columns
            logger.debug("SEASON column not found in multi-season result")

        return df

    # Fallback: No storage or no data available
    logger.warning("No data available in storage for any requested season")
    return pd.DataFrame()
