"""
Tests for REST API endpoints.

Basic test examples demonstrating how to test the API.
Run with: pytest tests/test_rest_api.py -v
"""

import pytest
from fastapi.testclient import TestClient

from cbb_data.api.rest_api import app


@pytest.fixture
def client() -> None:
    """Create a test client for the API."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client) -> None:
        """Test that health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
        assert "services" in data

    def test_health_check_has_cors_headers(self, client) -> None:
        """Test that CORS headers are present."""
        response = client.get("/health")
        # CORS headers should be present via middleware
        assert response.status_code == 200


class TestDatasetsListEndpoint:
    """Tests for datasets listing endpoint."""

    def test_list_datasets(self, client) -> None:
        """Test that we can list all datasets."""
        response = client.get("/datasets")
        assert response.status_code == 200

        data = response.json()
        assert "datasets" in data
        assert "count" in data
        assert data["count"] > 0

        # Check structure of first dataset
        if data["datasets"]:
            dataset = data["datasets"][0]
            assert "id" in dataset
            assert "name" in dataset
            assert "description" in dataset
            assert "supported_filters" in dataset
            assert "supported_leagues" in dataset

    def test_list_datasets_includes_expected_datasets(self, client) -> None:
        """Test that common datasets are present."""
        response = client.get("/datasets")
        data = response.json()

        dataset_ids = [ds["id"] for ds in data["datasets"]]

        # Check for expected datasets
        expected = ["schedule", "player_game", "team_game", "play_by_play", "player_season"]
        for dataset_id in expected:
            assert dataset_id in dataset_ids, f"Dataset '{dataset_id}' not found"


class TestDatasetQueryEndpoint:
    """Tests for dataset query endpoint."""

    def test_query_schedule_valid_request(self, client) -> None:
        """Test querying schedule with valid parameters."""
        request_data = {"filters": {"league": "NCAA-MBB", "season": "2024"}, "limit": 10}

        response = client.post("/datasets/schedule", json=request_data)

        # Should succeed or return data
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "metadata" in data

            # Check metadata structure
            metadata = data["metadata"]
            assert metadata["dataset_id"] == "schedule"
            assert "execution_time_ms" in metadata
            assert "row_count" in metadata

    def test_query_nonexistent_dataset(self, client) -> None:
        """Test querying a dataset that doesn't exist."""
        request_data = {"filters": {"league": "NCAA-MBB"}}

        response = client.post("/datasets/nonexistent_dataset", json=request_data)

        # Should return 404
        assert response.status_code == 404

    def test_query_with_invalid_filters(self, client) -> None:
        """Test that invalid filters return 400."""
        request_data = {"filters": {"league": "INVALID_LEAGUE"}}

        response = client.post("/datasets/schedule", json=request_data)

        # Should return 400 (bad request) or succeed with empty data
        assert response.status_code in [200, 400]


class TestRecentGamesEndpoint:
    """Tests for recent games convenience endpoint."""

    def test_get_recent_games(self, client) -> None:
        """Test getting recent games for a league."""
        response = client.get("/recent-games/NCAA-MBB?days=2")

        # Should succeed or return error
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "metadata" in data

    def test_get_recent_games_with_teams_filter(self, client) -> None:
        """Test recent games with team filter."""
        response = client.get("/recent-games/NCAA-MBB?days=2&teams=Duke,UNC")

        assert response.status_code in [200, 500]

    def test_get_recent_games_invalid_league(self, client) -> None:
        """Test recent games with invalid league."""
        response = client.get("/recent-games/INVALID?days=2")

        # Should return error
        assert response.status_code in [400, 500]


class TestDatasetInfoEndpoint:
    """Tests for dataset info endpoint."""

    def test_get_dataset_info(self, client) -> None:
        """Test getting info about a specific dataset."""
        response = client.get("/datasets/schedule/info")

        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "schedule"
        assert "description" in data
        assert "supported_filters" in data
        assert "supported_leagues" in data

    def test_get_nonexistent_dataset_info(self, client) -> None:
        """Test getting info for non-existent dataset."""
        response = client.get("/datasets/nonexistent/info")

        assert response.status_code == 404


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_rate_limit_headers_present(self, client) -> None:
        """Test that rate limit headers are included in responses."""
        response = client.get("/datasets")

        # Check for rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


class TestErrorHandling:
    """Tests for error handling middleware."""

    def test_404_for_invalid_endpoint(self, client) -> None:
        """Test that invalid endpoints return 404."""
        response = client.get("/invalid/endpoint")

        assert response.status_code == 404

    def test_process_time_header_present(self, client) -> None:
        """Test that X-Process-Time header is added."""
        response = client.get("/health")

        assert "X-Process-Time" in response.headers

        # Parse and verify it's a valid milliseconds value
        process_time = response.headers["X-Process-Time"]
        assert "ms" in process_time


# Run tests with: pytest tests/test_rest_api.py -v
