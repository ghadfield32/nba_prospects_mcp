"""
REST API module for college basketball data.

Provides HTTP endpoints for accessing basketball datasets via FastAPI.
"""

from .app import app
from .models import DatasetRequest, DatasetResponse, HealthResponse

__all__ = ["app", "DatasetRequest", "DatasetResponse", "HealthResponse"]
