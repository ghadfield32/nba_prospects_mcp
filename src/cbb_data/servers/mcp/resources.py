"""
MCP Resource definitions for browsable data catalogs.

Resources allow LLMs to explore available datasets, leagues, and
metadata without invoking tools.
"""

import logging
from typing import Any

from cbb_data.api.datasets import list_datasets

logger = logging.getLogger(__name__)


# ============================================================================
# Resource Handlers
# ============================================================================


def resource_list_datasets() -> dict[str, Any]:
    """
    List all available datasets.

    Returns:
        Dict with list of dataset metadata
    """
    try:
        datasets = list_datasets()
        return {"uri": "cbb://datasets/", "mimeType": "application/json", "text": str(datasets)}
    except Exception as e:
        logger.error(f"Error listing datasets: {e}", exc_info=True)
        return {"uri": "cbb://datasets/", "mimeType": "text/plain", "text": f"Error: {str(e)}"}


def resource_get_dataset_info(dataset_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific dataset.

    Args:
        dataset_id: ID of dataset to get info for

    Returns:
        Dict with dataset metadata
    """
    try:
        datasets = list_datasets()
        dataset = next((ds for ds in datasets if ds["id"] == dataset_id), None)

        if not dataset:
            return {
                "uri": f"cbb://datasets/{dataset_id}",
                "mimeType": "text/plain",
                "text": f"Dataset '{dataset_id}' not found",
            }

        # Format as readable text
        info = f"""# {dataset['id']}

**Description**: {dataset.get('description', 'N/A')}

**Primary Keys**: {', '.join(dataset.get('keys', []))}

**Supported Filters**: {', '.join(dataset.get('supports', []))}

**Supported Leagues**: {', '.join(dataset.get('leagues', []))}

**Data Sources**: {', '.join(dataset.get('sources', []))}

**Sample Columns**: {', '.join(dataset.get('sample_columns', [])[:10])}

**Requires Game ID**: {dataset.get('requires_game_id', False)}
"""

        return {"uri": f"cbb://datasets/{dataset_id}", "mimeType": "text/markdown", "text": info}

    except Exception as e:
        logger.error(f"Error getting dataset info: {e}", exc_info=True)
        return {
            "uri": f"cbb://datasets/{dataset_id}",
            "mimeType": "text/plain",
            "text": f"Error: {str(e)}",
        }


def resource_get_league_info(league: str) -> dict[str, Any]:
    """
    Get information about a specific league.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)

    Returns:
        Dict with league metadata
    """
    league_info = {
        "NCAA-MBB": {
            "name": "NCAA Men's Basketball",
            "description": "NCAA Division I, II, and III Men's College Basketball",
            "historical_data": "2002-present",
            "divisions": ["D1", "D2", "D3"],
            "data_sources": ["ESPN", "CBBpy", "Sports-Reference"],
            "available_datasets": [
                "schedule",
                "player_game",
                "team_game",
                "play_by_play",
                "shots",
                "player_season",
                "team_season",
                "player_team_season",
            ],
            "notes": "Comprehensive coverage of all NCAA divisions with historical data back to 2002.",
        },
        "NCAA-WBB": {
            "name": "NCAA Women's Basketball",
            "description": "NCAA Division I, II, and III Women's College Basketball",
            "historical_data": "2005-present",
            "divisions": ["D1", "D2", "D3"],
            "data_sources": ["ESPN", "CBBpy"],
            "available_datasets": [
                "schedule",
                "player_game",
                "team_game",
                "play_by_play",
                "player_season",
                "team_season",
            ],
            "notes": "Growing coverage of women's basketball with focus on D1.",
        },
        "EuroLeague": {
            "name": "EuroLeague Basketball",
            "description": "Top-tier European professional basketball league",
            "historical_data": "2001-present",
            "divisions": [],
            "data_sources": ["EuroLeague Official API"],
            "available_datasets": [
                "schedule",
                "player_game",
                "team_game",
                "play_by_play",
                "shots",
                "player_season",
                "team_season",
            ],
            "notes": "Official EuroLeague data with comprehensive stats and play-by-play.",
        },
    }

    info = league_info.get(league)
    if not info:
        return {
            "uri": f"cbb://leagues/{league}",
            "mimeType": "text/plain",
            "text": f"League '{league}' not found. Available: NCAA-MBB, NCAA-WBB, EuroLeague",
        }

    # Format as markdown
    text = f"""# {info['name']}

**Description**: {info['description']}

**Historical Data**: {info['historical_data']}

**Divisions**: {', '.join(info['divisions']) if info['divisions'] else 'N/A'}

**Data Sources**: {', '.join(info['data_sources'])}

**Available Datasets**:
{chr(10).join(f"- {ds}" for ds in info['available_datasets'])}

**Notes**: {info['notes']}
"""

    return {"uri": f"cbb://leagues/{league}", "mimeType": "text/markdown", "text": text}


# ============================================================================
# Resource Registry for MCP Server
# ============================================================================

RESOURCES = [
    {
        "uri": "cbb://datasets/",
        "name": "Available Datasets",
        "description": "List of all available basketball datasets",
        "mimeType": "application/json",
        "handler": lambda: resource_list_datasets(),
    },
    {
        "uri": "cbb://datasets/{dataset_id}",
        "name": "Dataset Info",
        "description": "Detailed information about a specific dataset",
        "mimeType": "text/markdown",
        "handler": lambda dataset_id: resource_get_dataset_info(dataset_id),
    },
    {
        "uri": "cbb://leagues/{league}",
        "name": "League Info",
        "description": "Information about a specific league",
        "mimeType": "text/markdown",
        "handler": lambda league: resource_get_league_info(league),
    },
]


# Static resources for common lookups
STATIC_RESOURCES = [
    {
        "uri": "cbb://leagues/NCAA-MBB",
        "name": "NCAA Men's Basketball",
        "description": "NCAA Men's Basketball league information",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://leagues/NCAA-WBB",
        "name": "NCAA Women's Basketball",
        "description": "NCAA Women's Basketball league information",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://leagues/EuroLeague",
        "name": "EuroLeague",
        "description": "EuroLeague basketball information",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/schedule",
        "name": "Schedule Dataset",
        "description": "Game schedules and results",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/player_game",
        "name": "Player Game Stats Dataset",
        "description": "Per-player per-game box scores",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/team_game",
        "name": "Team Game Stats Dataset",
        "description": "Team-level game results",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/play_by_play",
        "name": "Play-by-Play Dataset",
        "description": "Play-by-play event data",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/shots",
        "name": "Shot Chart Dataset",
        "description": "Shot location data with coordinates",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/player_season",
        "name": "Player Season Stats Dataset",
        "description": "Per-player season aggregates",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/team_season",
        "name": "Team Season Stats Dataset",
        "description": "Per-team season aggregates",
        "mimeType": "text/markdown",
    },
    {
        "uri": "cbb://datasets/player_team_season",
        "name": "Player-Team Season Dataset",
        "description": "Player stats by team (tracks transfers)",
        "mimeType": "text/markdown",
    },
]
