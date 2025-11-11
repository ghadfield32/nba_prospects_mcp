"""
Middleware for REST API.

Handles CORS, error handling, rate limiting, and request logging.
"""

import time
import logging
from typing import Callable, Dict, Any
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .models import ErrorResponse

# Configure logging
logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Catches all unhandled exceptions and returns consistent error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
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
                detail={"path": request.url.path, "method": request.method}
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error.model_dump()
            )

        except KeyError as e:
            # Handle missing required parameters
            logger.warning(f"Missing parameter on {request.url.path}: {str(e)}")
            error = ErrorResponse(
                error="MissingParameterError",
                message=f"Required parameter missing: {str(e)}",
                detail={"path": request.url.path, "method": request.method}
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error.model_dump()
            )

        except FileNotFoundError as e:
            # Handle resource not found errors
            logger.warning(f"Resource not found on {request.url.path}: {str(e)}")
            error = ErrorResponse(
                error="NotFoundError",
                message=str(e),
                detail={"path": request.url.path, "method": request.method}
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error.model_dump()
            )

        except Exception as e:
            # Handle all other unexpected errors
            logger.error(
                f"Unexpected error on {request.url.path}: {str(e)}",
                exc_info=True
            )
            error = ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred",
                detail={
                    "path": request.url.path,
                    "method": request.method,
                    "error_type": type(e).__name__
                }
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error.model_dump()
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.

    Limits requests per client IP address. For production use, consider
    using Redis-based rate limiting for distributed systems.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests allowed per minute per IP
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
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
            ts for ts in self.request_counts[client_ip]
            if ts > cutoff
        ]

        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            error = ErrorResponse(
                error="RateLimitExceeded",
                message=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                detail={
                    "retry_after_seconds": 60,
                    "client_ip": client_ip
                }
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=error.model_dump(),
                headers={"Retry-After": "60"}
            )

        # Record this request
        self.request_counts[client_ip].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.request_counts[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(
            int((now + timedelta(minutes=1)).timestamp())
        )

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Request logging middleware.

    Logs all incoming requests with method, path, and status code.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request and response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from handler
        """
        # Log request
        logger.info(f"{request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Log response
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code}"
        )

        return response


def configure_cors(app, allowed_origins: list = None):
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
            "X-RateLimit-Reset"
        ]
    )

    logger.info(f"CORS configured with allowed origins: {allowed_origins}")


def add_middleware(app, config: Dict[str, Any] = None):
    """
    Add all middleware to the application.

    Args:
        app: FastAPI application
        config: Optional configuration dict with keys:
            - cors_origins: List of allowed CORS origins
            - rate_limit: Requests per minute limit
            - enable_logging: Enable request logging
    """
    if config is None:
        config = {}

    # Configure CORS
    cors_origins = config.get("cors_origins", ["*"])
    configure_cors(app, cors_origins)

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
