"""Rate limiting utilities

This module provides rate limiting for API calls to respect source limits:
- Sports-Reference: ~1 req/sec (robots.txt compliance)
- ESPN: burst allowed, respect 429 responses
- EuroLeague: documented limits TBD
- NCAA API: unknown, conservative defaults
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Token bucket rate limiter

    Implements a token bucket algorithm for rate limiting:
    - Tokens are added at a constant rate (refill_rate)
    - Each request consumes one token
    - If no tokens available, caller must wait

    This is thread-safe and can be shared across multiple fetchers.

    Example:
        # Allow 1 request per second
        limiter = RateLimiter(calls_per_second=1.0)

        for url in urls:
            limiter.acquire()  # blocks if rate exceeded
            response = requests.get(url)
    """

    def __init__(
        self,
        calls_per_second: float = 1.0,
        burst_size: int | None = None,
    ):
        """Initialize rate limiter

        Args:
            calls_per_second: Maximum sustained rate (default 1.0)
            burst_size: Maximum burst capacity (default: calls_per_second * 2)
        """
        self.rate = calls_per_second
        self.burst_size = burst_size or int(calls_per_second * 2)
        self.tokens = float(self.burst_size)
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.rate
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_refill = now

    def acquire(self, block: bool = True, timeout: float | None = None) -> bool:
        """Acquire a token (may block if rate limit exceeded)

        Args:
            block: If True, wait for a token. If False, return immediately.
            timeout: Maximum wait time in seconds (None = wait forever)

        Returns:
            True if token acquired, False if timeout/non-blocking failure
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._refill()

                if self.tokens >= 1.0:
                    # Token available; consume it
                    self.tokens -= 1.0
                    return True

            # No token available
            if not block:
                return False

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False

            # Wait before retrying (but not too long)
            wait_time = min(1.0 / self.rate, 0.1)
            time.sleep(wait_time)

    def reset(self) -> None:
        """Reset the rate limiter (refill all tokens)"""
        with self.lock:
            self.tokens = float(self.burst_size)
            self.last_refill = time.time()


class SourceRateLimiter:
    """Per-source rate limiting

    Manages separate rate limiters for each data source.
    This allows us to respect different rate limits per source.

    Example:
        limiter = SourceRateLimiter()

        # Configure source-specific limits
        limiter.set_limit("sportsref", calls_per_second=1.0)
        limiter.set_limit("espn", calls_per_second=10.0)

        # Use in fetchers
        limiter.acquire("sportsref")
        data = fetch_sportsref_page()
    """

    # Default rate limits per source (conservative)
    DEFAULT_LIMITS = {
        "espn": 5.0,  # ESPN is generally permissive
        "sportsref": 1.0,  # Sports-Ref: be respectful
        "euroleague": 2.0,  # EuroLeague: moderate
        "ncaa": 2.0,  # NCAA: unknown, be conservative
        "nbl": 2.0,  # NBL: unknown
        "fiba": 1.0,  # FIBA: unknown, be conservative
    }

    def __init__(self) -> None:
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

        # Initialize default limiters
        for source, rate in self.DEFAULT_LIMITS.items():
            self._limiters[source] = RateLimiter(calls_per_second=rate)

    def set_limit(
        self, source: str, calls_per_second: float, burst_size: int | None = None
    ) -> None:
        """Set rate limit for a source

        Args:
            source: Source identifier
            calls_per_second: Rate limit
            burst_size: Optional burst capacity
        """
        with self._lock:
            self._limiters[source] = RateLimiter(
                calls_per_second=calls_per_second,
                burst_size=burst_size,
            )

    def acquire(self, source: str, block: bool = True, timeout: float | None = None) -> bool:
        """Acquire a token for a source

        Args:
            source: Source identifier
            block: Whether to block if rate exceeded
            timeout: Maximum wait time

        Returns:
            True if token acquired, False otherwise
        """
        # Get or create limiter for this source
        with self._lock:
            if source not in self._limiters:
                # Unknown source; use conservative default (1 req/sec)
                self._limiters[source] = RateLimiter(calls_per_second=1.0)

            limiter = self._limiters[source]

        return limiter.acquire(block=block, timeout=timeout)

    def reset(self, source: str | None = None) -> None:
        """Reset rate limiter(s)

        Args:
            source: Specific source to reset, or None for all sources
        """
        with self._lock:
            if source:
                if source in self._limiters:
                    self._limiters[source].reset()
            else:
                for limiter in self._limiters.values():
                    limiter.reset()


# Global source rate limiter instance
_source_limiter = SourceRateLimiter()


def get_source_limiter() -> SourceRateLimiter:
    """Get the global source rate limiter"""
    return _source_limiter


def set_source_limit(source: str, calls_per_second: float) -> None:
    """Set rate limit for a source (convenience function)

    Args:
        source: Source identifier
        calls_per_second: Rate limit
    """
    _source_limiter.set_limit(source, calls_per_second)
