"""
Middleware for REST API.

Handles CORS, error handling, rate limiting, request logging, request tracking
circuit breaking, and idempotency.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .models import ErrorResponse

# Import our logging and metrics modules
try:
    from cbb_data.servers.logging import log_request
    from cbb_data.servers.metrics import track_http_request

    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Catches all unhandled exceptions and returns consistent error responses.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process request and handle any errors.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with error details if exception occurred
        """
        try:
            # Add request start time for performance tracking
            request.state.start_time = time.time()

            # Process request
            response = await call_next(request)

            # Add performance header
            if hasattr(request.state, "start_time"):
                process_time = (time.time() - request.state.start_time) * 1000
                response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

            return response

        except ValueError as e:
            # Handle validation errors
            logger.warning(f"Validation error on {request.url.path}: {str(e)}")
            error = ErrorResponse(
                error="ValidationError",
                message=str(e),
                detail={"path": request.url.path, "method": request.method},
            )
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=error.model_dump())

        except KeyError as e:
            # Handle missing required parameters
            logger.warning(f"Missing parameter on {request.url.path}: {str(e)}")
            error = ErrorResponse(
                error="MissingParameterError",
                message=f"Required parameter missing: {str(e)}",
                detail={"path": request.url.path, "method": request.method},
            )
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=error.model_dump())

        except FileNotFoundError as e:
            # Handle resource not found errors
            logger.warning(f"Resource not found on {request.url.path}: {str(e)}")
            error = ErrorResponse(
                error="NotFoundError",
                message=str(e),
                detail={"path": request.url.path, "method": request.method},
            )
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error.model_dump())

        except Exception as e:
            # Handle all other unexpected errors
            logger.error(f"Unexpected error on {request.url.path}: {str(e)}", exc_info=True)
            error = ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred",
                detail={
                    "path": request.url.path,
                    "method": request.method,
                    "error_type": type(e).__name__,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error.model_dump()
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.

    Limits requests per client IP address. For production use, consider
    using Redis-based rate limiting for distributed systems.
    """

    def __init__(self, app: Any, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests allowed per minute per IP
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: dict[str, list] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Check rate limit and process request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response or rate limit error
        """
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Clean up old timestamps (older than 1 minute)
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        self.request_counts[client_ip] = [
            ts for ts in self.request_counts[client_ip] if ts > cutoff
        ]

        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            error = ErrorResponse(
                error="RateLimitExceeded",
                message=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                detail={"retry_after_seconds": 60, "client_ip": client_ip},
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=error.model_dump(),
                headers={"Retry-After": "60"},
            )

        # Record this request
        self.request_counts[client_ip].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.request_counts[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int((now + timedelta(minutes=1)).timestamp()))

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Request logging middleware.

    Logs all incoming requests with method, path, and status code.
    Uses structured JSON logging if available.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Log request and response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from handler
        """
        # Get request ID if available
        request_id = getattr(request.state, "request_id", None)

        # Log request
        logger.info(f"{request.method} {request.url.path}")

        # Track start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        duration_seconds = duration_ms / 1000

        # Log response
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms:.2f}ms)"
        )

        # Structured logging if available
        if OBSERVABILITY_AVAILABLE:
            log_request(
                service="rest",
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=request_id,
            )
            track_http_request(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
                duration_seconds=duration_seconds,
            )

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Request ID tracking middleware.

    Adds a unique request ID to each request for tracing across systems.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Add request ID to request state and response headers.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with X-Request-ID header
        """
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in request state for other middleware/handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded threshold, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Circuit breaker middleware for upstream API protection.

    Tracks failures and opens circuit to prevent cascading failures.
    Automatically recovers with exponential backoff.
    """

    def __init__(
        self,
        app: Any,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_requests: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            app: FastAPI application
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Seconds to wait before trying half-open
            half_open_max_requests: Max requests in half-open state
        """
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_requests = half_open_max_requests

        # Circuit state per upstream (tracked by endpoint pattern)
        self.state: dict[str, CircuitBreakerState] = defaultdict(lambda: CircuitBreakerState.CLOSED)
        self.failure_count: dict[str, int] = defaultdict(int)
        self.last_failure_time: dict[str, datetime] = {}
        self.half_open_requests: dict[str, int] = defaultdict(int)

    def _get_circuit_key(self, path: str) -> str:
        """Get circuit key from path (group similar endpoints)."""
        # Group by dataset endpoint
        if path.startswith("/datasets/"):
            return "/datasets/*"
        return path

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Check circuit state and process request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response or circuit breaker error
        """
        circuit_key = self._get_circuit_key(request.url.path)
        current_state = self.state[circuit_key]

        # Check if circuit is OPEN
        if current_state == CircuitBreakerState.OPEN:
            # Check if timeout expired (move to HALF_OPEN)
            last_failure = self.last_failure_time.get(circuit_key)
            if last_failure:
                time_since_failure = (datetime.utcnow() - last_failure).total_seconds()
                if time_since_failure >= self.timeout_seconds:
                    # Move to HALF_OPEN
                    self.state[circuit_key] = CircuitBreakerState.HALF_OPEN
                    self.half_open_requests[circuit_key] = 0
                    logger.info(f"Circuit breaker {circuit_key} moved to HALF_OPEN")
                else:
                    # Still open, reject request
                    retry_after = int(self.timeout_seconds - time_since_failure)
                    logger.warning(
                        f"Circuit breaker {circuit_key} is OPEN (retry in {retry_after}s)"
                    )
                    error = ErrorResponse(
                        error="CircuitBreakerOpen",
                        message="Service temporarily unavailable (circuit breaker open)",
                        detail={"retry_after_seconds": retry_after, "upstream": circuit_key},
                    )
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content=error.model_dump(),
                        headers={"Retry-After": str(retry_after)},
                    )

        # Check if circuit is HALF_OPEN
        if current_state == CircuitBreakerState.HALF_OPEN:
            # Limit requests in half-open state
            if self.half_open_requests[circuit_key] >= self.half_open_max_requests:
                logger.warning(f"Circuit breaker {circuit_key} HALF_OPEN limit reached")
                error = ErrorResponse(
                    error="CircuitBreakerHalfOpen",
                    message="Service recovering, please retry shortly",
                    detail={"retry_after_seconds": 5, "upstream": circuit_key},
                )
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content=error.model_dump(),
                    headers={"Retry-After": "5"},
                )

            self.half_open_requests[circuit_key] += 1

        # Process request
        try:
            response = await call_next(request)

            # Check if response indicates upstream failure (5xx)
            if response.status_code >= 500:
                self._record_failure(circuit_key)
            else:
                # Success - reset circuit if half-open
                if current_state == CircuitBreakerState.HALF_OPEN:
                    self._record_success(circuit_key)

            return response

        except Exception:
            # Exception during request processing
            self._record_failure(circuit_key)
            raise

    def _record_failure(self, circuit_key: str) -> None:
        """Record a failure and potentially open circuit."""
        self.failure_count[circuit_key] += 1
        self.last_failure_time[circuit_key] = datetime.utcnow()

        if self.failure_count[circuit_key] >= self.failure_threshold:
            # Open circuit
            self.state[circuit_key] = CircuitBreakerState.OPEN
            logger.error(
                f"Circuit breaker {circuit_key} OPENED after {self.failure_count[circuit_key]} failures"
            )

    def _record_success(self, circuit_key: str) -> None:
        """Record a success and close circuit if half-open."""
        if self.state[circuit_key] == CircuitBreakerState.HALF_OPEN:
            # Close circuit
            self.state[circuit_key] = CircuitBreakerState.CLOSED
            self.failure_count[circuit_key] = 0
            self.half_open_requests[circuit_key] = 0
            logger.info(f"Circuit breaker {circuit_key} CLOSED (recovered)")


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Idempotency middleware for de-duplicating rapid repeated requests.

    Caches responses for identical requests within a time window to prevent
    double-execution from LLM retries or network issues.
    """

    def __init__(self, app: Any, window_ms: int = 250):
        """
        Initialize idempotency middleware.

        Args:
            app: FastAPI application
            window_ms: Time window in milliseconds for de-duplication
        """
        super().__init__(app)
        self.window_ms = window_ms
        self.cache: dict[str, tuple[Response, datetime]] = {}

    def _get_request_hash(self, request: Request, body: bytes) -> str:
        """Generate hash of request for deduplication."""
        # Hash based on method + path + body
        content = f"{request.method}:{request.url.path}:{body.decode('utf-8', errors='ignore')}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Check cache and process request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response (possibly cached)
        """
        # Only apply to POST requests (mutations)
        if request.method != "POST":
            return await call_next(request)

        # Read body for hashing
        body = await request.body()

        # Generate request hash
        request_hash = self._get_request_hash(request, body)

        # Check cache
        now = datetime.utcnow()
        if request_hash in self.cache:
            cached_response, cached_time = self.cache[request_hash]
            age_ms = (now - cached_time).total_seconds() * 1000

            if age_ms < self.window_ms:
                # Return cached response
                logger.info(f"Idempotency: Returning cached response (age: {age_ms:.0f}ms)")
                cached_response.headers["X-Idempotency-Cache"] = "HIT"
                cached_response.headers["X-Idempotency-Age-Ms"] = f"{age_ms:.0f}"
                return cached_response

        # Clean up old cache entries
        cutoff = now - timedelta(milliseconds=self.window_ms * 2)
        self.cache = {k: v for k, v in self.cache.items() if v[1] > cutoff}

        # Process request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code < 400:
            self.cache[request_hash] = (response, now)
            response.headers["X-Idempotency-Cache"] = "MISS"

        return response


def configure_cors(app: Any, allowed_origins: list[Any] | None = None) -> None:
    """
    Configure CORS middleware for the application.

    Args:
        app: FastAPI application
        allowed_origins: List of allowed origins (default: allow all)
    """
    if allowed_origins is None:
        allowed_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Process-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
            "X-Idempotency-Cache",
            "X-Idempotency-Age-Ms",
        ],
    )

    logger.info(f"CORS configured with allowed origins: {allowed_origins}")


def add_middleware(app: Any, config: dict[str, Any] | None = None) -> None:
    """
    Add all middleware to the application.

    Middleware is added in reverse order (last added = first executed).
    Order: CORS → Request ID → Circuit Breaker → Idempotency → Rate Limit → Error Handling → Logging

    Args:
        app: FastAPI application
        config: Optional configuration dict with keys:
            - cors_origins: List of allowed CORS origins
            - rate_limit: Requests per minute limit
            - enable_logging: Enable request logging
            - enable_circuit_breaker: Enable circuit breaker (default: True)
            - enable_idempotency: Enable idempotency/de-dupe (default: True)
            - circuit_breaker_threshold: Failures before opening (default: 5)
            - circuit_breaker_timeout: Timeout in seconds (default: 60)
            - idempotency_window_ms: De-dupe window in milliseconds (default: 250)
    """
    if config is None:
        config = {}

    # Configure CORS (outermost middleware)
    cors_origins = config.get("cors_origins", ["*"])
    configure_cors(app, cors_origins)

    # Add Request ID tracking
    app.add_middleware(RequestIDMiddleware)
    logger.info("Request ID middleware configured")

    # Add Circuit Breaker (if enabled)
    if config.get("enable_circuit_breaker", True):
        threshold = config.get("circuit_breaker_threshold", 5)
        timeout = config.get("circuit_breaker_timeout", 60)
        app.add_middleware(
            CircuitBreakerMiddleware, failure_threshold=threshold, timeout_seconds=timeout
        )
        logger.info(f"Circuit breaker configured (threshold={threshold}, timeout={timeout}s)")

    # Add Idempotency/De-dupe (if enabled)
    if config.get("enable_idempotency", True):
        window_ms = config.get("idempotency_window_ms", 250)
        app.add_middleware(IdempotencyMiddleware, window_ms=window_ms)
        logger.info(f"Idempotency middleware configured (window={window_ms}ms)")

    # Add rate limiting
    rate_limit = config.get("rate_limit", 60)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)
    logger.info(f"Rate limiting configured: {rate_limit} requests/minute")

    # Add error handling
    app.add_middleware(ErrorHandlingMiddleware)
    logger.info("Error handling middleware configured")

    # Add request logging if enabled
    if config.get("enable_logging", True):
        app.add_middleware(RequestLoggingMiddleware)
        logger.info("Request logging middleware configured")
