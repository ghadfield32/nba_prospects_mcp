"""Play-by-play parsers for generating box scores from raw event data

This module transforms ESPN play-by-play data into structured player statistics,
enabling box score generation for NCAA games where ESPN's API returns empty statistics arrays.
"""

from cbb_data.parsers.pbp_parser import (
    extract_player_mapping,
    parse_game_to_box_score,
    parse_pbp_to_player_stats,
)

__all__ = [
    "parse_game_to_box_score",
    "extract_player_mapping",
    "parse_pbp_to_player_stats",
]
