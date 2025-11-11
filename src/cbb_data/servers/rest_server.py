"""
REST API Server startup script.

Launches the FastAPI application with uvicorn for HTTP access.

Usage:
    # Development mode with auto-reload
    python -m cbb_data.servers.rest_server

    # Production mode
    python -m cbb_data.servers.rest_server --host 0.0.0.0 --port 8000 --workers 4

    # Custom configuration
    python -m cbb_data.servers.rest_server --port 3000 --reload
"""

import argparse
import logging
import sys
from typing import Optional

try:
    import uvicorn
except ImportError:
    print("ERROR: uvicorn is not installed. Install it with:")
    print("  pip install uvicorn[standard]")
    print("  or: uv pip install uvicorn[standard]")
    sys.exit(1)

from cbb_data.api.rest_api import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Start the College Basketball Data REST API server"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1, use 0.0.0.0 for all interfaces)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1, use >1 for production)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
        help="Log level (default: info)"
    )

    return parser.parse_args()


def main():
    """Main entry point for REST API server."""
    args = parse_args()

    logger.info("=" * 70)
    logger.info("College Basketball Data REST API Server")
    logger.info("=" * 70)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Reload: {args.reload}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info("=" * 70)
    logger.info(f"API Docs: http://{args.host}:{args.port}/docs")
    logger.info(f"ReDoc: http://{args.host}:{args.port}/redoc")
    logger.info(f"OpenAPI JSON: http://{args.host}:{args.port}/openapi.json")
    logger.info("=" * 70)
    logger.info("Press CTRL+C to stop the server")
    logger.info("=" * 70)

    try:
        # Configure uvicorn
        uvicorn_config = {
            "app": "cbb_data.api.rest_api:app",
            "host": args.host,
            "port": args.port,
            "log_level": args.log_level,
        }

        # Add development mode settings
        if args.reload:
            uvicorn_config["reload"] = True
            logger.info("⚠️  Running in DEVELOPMENT mode with auto-reload")

        # Add production settings
        if args.workers > 1:
            if args.reload:
                logger.warning(
                    "⚠️  Cannot use --reload with multiple workers. "
                    "Using single worker."
                )
                uvicorn_config["workers"] = 1
            else:
                uvicorn_config["workers"] = args.workers
                logger.info(f"Running with {args.workers} worker processes")

        # Start server
        uvicorn.run(**uvicorn_config)

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 70)
        logger.info("Server stopped by user")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
