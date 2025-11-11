"""Base fetcher with caching and retry logic

This module provides the core infrastructure for all data fetchers:
- TTL-based caching (memory + optional Redis)
- Retry logic with exponential backoff
- Rate limiting hooks
- Error handling and logging
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from io import StringIO
from typing import Any, TypeVar

import pandas as pd

# Try to import Redis; it's optional
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

T = TypeVar("T")


class Cache:
    """Simple TTL cache with memory + optional Redis backend

    The cache uses a two-tier strategy:
    1. In-memory cache (dict) for fast access
    2. Redis (optional) for persistence across processes

    Cache keys are SHA256 hashes of (function_name, json_params)
    """

    def __init__(self, ttl_seconds: int = 3600, redis_enabled: bool | None = None):
        """Initialize cache

        Args:
            ttl_seconds: Time-to-live for cache entries (default 1 hour)
            redis_enabled: Override Redis detection (default: auto-detect via env)
        """
        self.ttl = ttl_seconds
        self._mem: dict[str, tuple[float, Any]] = {}
        self._redis: Any | None = None

        # Determine if Redis should be enabled
        if redis_enabled is None:
            redis_enabled = os.getenv("ENABLE_REDIS_CACHE", "false").lower() == "true"

        if redis_enabled and REDIS_AVAILABLE:
            try:
                host = os.getenv("REDIS_HOST", "localhost")
                port = int(os.getenv("REDIS_PORT", "6379"))
                db = int(os.getenv("REDIS_DB", "0"))
                self._redis = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    decode_responses=False,
                    socket_connect_timeout=2,
                )
                # Test connection
                self._redis.ping()
                logger.info(f"Redis cache enabled: {host}:{port}/{db}")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache only: {e}")
                self._redis = None
        else:
            logger.info("Using memory-only cache")

    def _key(self, *parts: Any) -> str:
        """Generate cache key from parts"""
        key_str = "|".join(str(p) for p in parts)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, *parts: Any) -> Any | None:
        """Get cached value if exists and not expired"""
        key = self._key(*parts)
        now = time.time()

        # Try Redis first (if available)
        if self._redis:
            try:
                blob = self._redis.get(key)
                if blob:
                    ts, payload = json.loads(blob.decode("utf-8"))
                    if now - ts <= self.ttl:
                        logger.debug(f"Cache hit (Redis): {key[:12]}...")
                        return payload
                    else:
                        # Expired; delete
                        self._redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        # Try memory cache
        if key in self._mem:
            ts, payload = self._mem[key]
            if now - ts <= self.ttl:
                logger.debug(f"Cache hit (memory): {key[:12]}...")
                return payload
            else:
                # Expired; delete
                del self._mem[key]

        logger.debug(f"Cache miss: {key[:12]}...")
        return None

    def set(self, value: Any, *parts: Any) -> None:
        """Set cache value"""
        key = self._key(*parts)
        now = time.time()

        # Store in Redis (if available)
        if self._redis:
            try:
                blob = json.dumps([now, value]).encode("utf-8")
                self._redis.set(key, blob)
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Always store in memory as fallback
        self._mem[key] = (now, value)

    def clear(self) -> None:
        """Clear all cache entries"""
        self._mem.clear()
        if self._redis:
            try:
                self._redis.flushdb()
                logger.info("Cache cleared (memory + Redis)")
            except Exception as e:
                logger.warning(f"Redis flush error: {e}")
        else:
            logger.info("Cache cleared (memory)")

    def stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        mem_size = len(self._mem)
        redis_size = None
        if self._redis:
            try:
                redis_size = self._redis.dbsize()
            except Exception:
                pass

        return {
            "memory_entries": mem_size,
            "redis_entries": redis_size,
            "ttl_seconds": self.ttl,
            "redis_enabled": self._redis is not None,
        }


# Global cache instance (can be reconfigured)
_cache = Cache(ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")))


def get_cache() -> Cache:
    """Get the global cache instance"""
    return _cache


def set_cache(cache: Cache) -> None:
    """Set a custom cache instance"""
    global _cache
    _cache = cache


def cached_dataframe(fn: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
    """Decorator to cache DataFrame-returning functions

    The cache key includes the function name and all kwargs (serialized as JSON).
    DataFrames are cached as JSON (orient='split') for fast serialization.

    Example:
        @cached_dataframe
        def fetch_games(season: str, team_id: int) -> pd.DataFrame:
            # expensive API call
            return df
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> pd.DataFrame:
        # Create cache key from function name + kwargs
        cache_key = (fn.__name__, json.dumps(kwargs, sort_keys=True, default=str))

        # Try to get from cache
        cached = _cache.get(*cache_key)
        if cached is not None:
            try:
                # Use StringIO to avoid pandas FutureWarning about passing literal JSON
                return pd.read_json(StringIO(cached), orient="split")
            except Exception as e:
                logger.warning(f"Cache deserialization error: {e}")

        # Cache miss; call function
        logger.debug(f"Fetching: {fn.__name__}({kwargs})")
        df = fn(*args, **kwargs)

        # Store in cache
        try:
            serialized = df.to_json(orient="split")
            _cache.set(serialized, *cache_key)
        except Exception as e:
            logger.warning(f"Cache serialization error: {e}")

        return df

    return wrapper


def retry_on_error(
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry function calls with exponential backoff

    Args:
        max_attempts: Maximum number of attempts (default 3)
        backoff_seconds: Initial backoff time, doubles each retry (default 1.0)
        exceptions: Tuple of exceptions to catch (default all Exception)

    Example:
        @retry_on_error(max_attempts=3, backoff_seconds=2.0)
        def fetch_data():
            # may fail transiently
            return requests.get(url).json()
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait = backoff_seconds * (2 ** (attempt - 1))
                        logger.warning(
                            f"{fn.__name__} failed (attempt {attempt}/{max_attempts}), "
                            f"retrying in {wait:.1f}s: {e}"
                        )
                        time.sleep(wait)
                    else:
                        logger.error(f"{fn.__name__} failed after {max_attempts} attempts: {e}")

            # All attempts failed
            raise last_exception  # type: ignore

        return wrapper

    return decorator


def rate_limited(calls_per_second: float = 1.0) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to rate-limit function calls

    Args:
        calls_per_second: Maximum calls per second (default 1.0)

    Example:
        @rate_limited(calls_per_second=2.0)
        def fetch_page(url: str):
            return requests.get(url)
    """
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            now = time.time()
            elapsed = now - last_called[0]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            last_called[0] = time.time()
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# Utility functions for common data operations


def normalize_columns(df: pd.DataFrame, rename_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Normalize DataFrame column names and types

    Args:
        df: Input DataFrame
        rename_map: Optional column rename mapping

    Returns:
        DataFrame with normalized columns
    """
    if df.empty:
        return df

    out = df.copy()

    # Apply custom renames
    if rename_map:
        out = out.rename(columns=rename_map)

    # Coerce common ID columns to Int64 (nullable integer)
    id_cols = [c for c in out.columns if c.endswith("_ID")]
    for col in id_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # Coerce date columns
    date_cols = [c for c in out.columns if "DATE" in c]
    for col in date_cols:
        if out[col].dtype == "object":
            out[col] = pd.to_datetime(out[col], errors="coerce")

    return out


def ensure_columns(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    """Ensure DataFrame has required columns (add as NaN if missing)

    Args:
        df: Input DataFrame
        required_cols: List of required column names

    Returns:
        DataFrame with all required columns
    """
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        for col in missing:
            df[col] = pd.NA
    return df
