"""
Configuration management for CBB Data servers.

Provides centralized configuration for REST API and MCP servers.
"""

import os

from pydantic import BaseModel, Field


class RESTAPIConfig(BaseModel):
    """Configuration for REST API server."""

    host: str = Field(default="127.0.0.1", description="Host to bind to")

    port: int = Field(default=8000, description="Port to bind to", ge=1, le=65535)

    reload: bool = Field(default=False, description="Enable auto-reload (development mode)")

    workers: int = Field(default=1, description="Number of worker processes", ge=1)

    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")

    rate_limit: int = Field(default=60, description="Requests per minute per IP", ge=1)

    log_level: str = Field(default="info", description="Logging level")

    @classmethod
    def from_env(cls) -> "RESTAPIConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            CBB_API_HOST: API host (default: 127.0.0.1)
            CBB_API_PORT: API port (default: 8000)
            CBB_API_RELOAD: Enable reload (default: false)
            CBB_API_WORKERS: Number of workers (default: 1)
            CBB_API_CORS_ORIGINS: Comma-separated origins (default: *)
            CBB_API_RATE_LIMIT: Rate limit (default: 60)
            CBB_API_LOG_LEVEL: Log level (default: info)

        Returns:
            RESTAPIConfig instance
        """
        cors_origins = os.getenv("CBB_API_CORS_ORIGINS", "*")
        if cors_origins == "*":
            cors_origins_list = ["*"]
        else:
            cors_origins_list = [o.strip() for o in cors_origins.split(",")]

        return cls(
            host=os.getenv("CBB_API_HOST", "127.0.0.1"),
            port=int(os.getenv("CBB_API_PORT", "8000")),
            reload=os.getenv("CBB_API_RELOAD", "false").lower() == "true",
            workers=int(os.getenv("CBB_API_WORKERS", "1")),
            cors_origins=cors_origins_list,
            rate_limit=int(os.getenv("CBB_API_RATE_LIMIT", "60")),
            log_level=os.getenv("CBB_API_LOG_LEVEL", "info"),
        )


class MCPServerConfig(BaseModel):
    """Configuration for MCP server."""

    transport: str = Field(default="stdio", description="Transport mode (stdio or sse)")

    host: str = Field(default="localhost", description="Host to bind to (SSE mode only)")

    port: int = Field(default=3000, description="Port to bind to (SSE mode only)", ge=1, le=65535)

    log_level: str = Field(default="info", description="Logging level")

    @classmethod
    def from_env(cls) -> "MCPServerConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            CBB_MCP_TRANSPORT: Transport mode (default: stdio)
            CBB_MCP_HOST: MCP host (SSE mode, default: localhost)
            CBB_MCP_PORT: MCP port (SSE mode, default: 3000)
            CBB_MCP_LOG_LEVEL: Log level (default: info)

        Returns:
            MCPServerConfig instance
        """
        return cls(
            transport=os.getenv("CBB_MCP_TRANSPORT", "stdio"),
            host=os.getenv("CBB_MCP_HOST", "localhost"),
            port=int(os.getenv("CBB_MCP_PORT", "3000")),
            log_level=os.getenv("CBB_MCP_LOG_LEVEL", "info"),
        )


class DataConfig(BaseModel):
    """Configuration for data fetching and caching."""

    cache_enabled: bool = Field(default=True, description="Enable DuckDB caching")

    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours", ge=1)

    max_concurrent_requests: int = Field(
        default=10, description="Maximum concurrent API requests", ge=1
    )

    request_timeout_seconds: int = Field(default=30, description="Request timeout in seconds", ge=1)

    # Auto-pagination settings
    max_rows: int = Field(default=2000, description="Maximum rows before auto-pagination", ge=1)

    max_tokens: int = Field(
        default=8000, description="Maximum tokens before stopping pagination", ge=100
    )

    # Per-dataset TTL (in seconds)
    ttl_schedule: int = Field(default=900, description="TTL for schedule data (15 min)", ge=1)

    ttl_pbp: int = Field(
        default=30, description="TTL for play-by-play data (30 sec for live games)", ge=1
    )

    ttl_shots: int = Field(default=60, description="TTL for shot data (1 min)", ge=1)

    ttl_default: int = Field(
        default=3600, description="Default TTL for other datasets (1 hour)", ge=1
    )

    # De-duplication window
    dedupe_window_ms: int = Field(
        default=250, description="De-duplication window in milliseconds", ge=0
    )

    @classmethod
    def from_env(cls) -> "DataConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            # Legacy
            CBB_CACHE_ENABLED: Enable caching (default: true)
            CBB_CACHE_TTL_HOURS: Cache TTL (default: 24)
            CBB_MAX_CONCURRENT: Max concurrent requests (default: 10)
            CBB_REQUEST_TIMEOUT: Request timeout (default: 30)

            # Auto-pagination
            CBB_MAX_ROWS: Max rows before pagination (default: 2000)
            CBB_MAX_TOKENS: Max tokens before stopping (default: 8000)

            # Per-dataset TTL (seconds)
            CBB_TTL_SCHEDULE: Schedule data TTL (default: 900)
            CBB_TTL_PBP: Play-by-play TTL (default: 30)
            CBB_TTL_SHOTS: Shot data TTL (default: 60)
            CBB_TTL_DEFAULT: Default TTL (default: 3600)

            # De-duplication
            CBB_DEDUPE_WINDOW_MS: De-dupe window ms (default: 250)

        Returns:
            DataConfig instance
        """
        return cls(
            cache_enabled=os.getenv("CBB_CACHE_ENABLED", "true").lower() == "true",
            cache_ttl_hours=int(os.getenv("CBB_CACHE_TTL_HOURS", "24")),
            max_concurrent_requests=int(os.getenv("CBB_MAX_CONCURRENT", "10")),
            request_timeout_seconds=int(os.getenv("CBB_REQUEST_TIMEOUT", "30")),
            # New settings
            max_rows=int(os.getenv("CBB_MAX_ROWS", "2000")),
            max_tokens=int(os.getenv("CBB_MAX_TOKENS", "8000")),
            ttl_schedule=int(os.getenv("CBB_TTL_SCHEDULE", "900")),
            ttl_pbp=int(os.getenv("CBB_TTL_PBP", "30")),
            ttl_shots=int(os.getenv("CBB_TTL_SHOTS", "60")),
            ttl_default=int(os.getenv("CBB_TTL_DEFAULT", "3600")),
            dedupe_window_ms=int(os.getenv("CBB_DEDUPE_WINDOW_MS", "250")),
        )


class Config(BaseModel):
    """Master configuration for all CBB Data components."""

    rest_api: RESTAPIConfig = Field(default_factory=RESTAPIConfig)
    mcp_server: MCPServerConfig = Field(default_factory=MCPServerConfig)
    data: DataConfig = Field(default_factory=DataConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load all configuration from environment variables.

        Returns:
            Config instance with all sub-configurations loaded
        """
        return cls(
            rest_api=RESTAPIConfig.from_env(),
            mcp_server=MCPServerConfig.from_env(),
            data=DataConfig.from_env(),
        )

    @classmethod
    def default(cls) -> "Config":
        """
        Get default configuration.

        Returns:
            Config instance with default values
        """
        return cls()


# Global configuration instance (loaded from environment)
config = Config.from_env()

__all__ = ["Config", "RESTAPIConfig", "MCPServerConfig", "DataConfig", "config"]
