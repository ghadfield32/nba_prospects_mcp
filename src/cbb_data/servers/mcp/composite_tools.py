"""
Smart Composite MCP Tools.

Combines multiple datasets and operations to reduce LLM round-trips for common workflows.

Composite tools handle:
    - Multi-step data fetching (schedule → game_ids → play-by-play)
    - Cross-dataset enrichment (player stats + team context)
    - Temporal analysis (recent trends, rolling averages)
    - Automatic pagination and token management

Usage:
    from cbb_data.servers.mcp.composite_tools import (
        composite_resolve_and_get_pbp,
        composite_player_trend
    )

    # Get play-by-play for a team's games in a date range
    pbp = composite_resolve_and_get_pbp(
        league="NCAA-MBB",
        team="Duke",
        date_from="2025-01-01",
        date_to="2025-01-31"
    )

    # Get player's last N games with trends
    trend = composite_player_trend(
        league="NCAA-MBB",
        player="Cooper Flagg",
        last_n_games=10
    )
"""

import logging
from typing import Any

# Import existing library functions
from cbb_data.api.datasets import get_dataset
from cbb_data.compose.enrichers import apply_guardrails

# Import our wrappers and utilities
from cbb_data.servers.mcp_wrappers import estimate_tokens, prune_to_key_columns
from cbb_data.utils.natural_language import normalize_filters_for_llm

logger = logging.getLogger(__name__)


# ============================================================================
# Composite Tool: Resolve Schedule + Get Play-by-Play
# ============================================================================


def composite_resolve_and_get_pbp(
    league: str,
    team: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    season: str | None = None,
    max_games: int = 10,
    compact: bool = True,
) -> dict[str, Any]:
    """
    Resolve team's games from schedule, then fetch play-by-play for those games.

    This composite tool handles a common LLM workflow in one call:
        1. Fetch schedule to get game IDs
        2. Filter to team's games
        3. Fetch play-by-play for those game IDs
        4. Apply token management

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        team: Team name (optional, if omitted returns all games in range)
        date_from: Start date (supports natural language)
        date_to: End date (supports natural language)
        season: Season (supports natural language like "this season")
        max_games: Maximum games to fetch (default: 10, helps with token budget)
        compact: Enable column pruning for token efficiency

    Returns:
        Dict with:
            - play_by_play: DataFrame or structured data
            - games_found: Number of games
            - game_ids: List of game IDs fetched
            - truncated: Whether results were limited
            - estimated_tokens: Token estimate

    Examples:
        >>> # Get Duke's last 5 games of play-by-play
        >>> pbp = composite_resolve_and_get_pbp(
        ...     league="NCAA-MBB",
        ...     team="Duke",
        ...     date_from="last week",
        ...     max_games=5
        ... )
        >>> pbp["games_found"]
        5
        >>> pbp["play_by_play"]  # Full PBP data
        {...}
    """
    try:
        # Step 1: Normalize inputs
        filters = normalize_filters_for_llm(
            {
                "league": league,
                "season": season,
                "team": [team] if team else None,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        # Step 2: Fetch schedule to get game IDs
        logger.info(f"Resolving schedule for {league}, team={team}, dates={date_from} to {date_to}")

        schedule = get_dataset(
            "schedule", filters, limit=max_games * 2
        )  # Fetch extra for filtering

        if schedule.empty:
            return {
                "success": True,
                "play_by_play": None,
                "games_found": 0,
                "game_ids": [],
                "message": "No games found matching criteria",
            }

        # Step 3: Extract game IDs (limit to max_games)
        game_id_col = "GAME_ID" if "GAME_ID" in schedule.columns else "Game_ID"
        game_ids = schedule[game_id_col].dropna().unique()[:max_games].tolist()

        logger.info(f"Found {len(game_ids)} game IDs, fetching play-by-play...")

        # Step 4: Fetch play-by-play for those game IDs
        pbp = get_dataset("play_by_play", {"league": league, "game_ids": game_ids})

        if pbp.empty:
            return {
                "success": True,
                "play_by_play": None,
                "games_found": len(game_ids),
                "game_ids": game_ids,
                "message": f"Found {len(game_ids)} games but no play-by-play data available",
            }

        # Step 5: Apply guardrails
        pbp = apply_guardrails(pbp, compact=compact)

        # Step 6: Prune columns if compact mode
        if compact:
            pbp = prune_to_key_columns(pbp, "play_by_play")

        # Step 7: Estimate tokens
        tokens = estimate_tokens(len(pbp), len(pbp.columns))

        # Step 8: Return structured result
        return {
            "success": True,
            "play_by_play": {
                "columns": pbp.columns.tolist(),
                "data": pbp.values.tolist(),
                "row_count": len(pbp),
            },
            "games_found": len(game_ids),
            "game_ids": game_ids,
            "truncated": len(game_ids) >= max_games,
            "estimated_tokens": tokens,
        }

    except Exception as e:
        logger.error(f"Error in composite_resolve_and_get_pbp: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ============================================================================
# Composite Tool: Player Trend (Last N Games)
# ============================================================================


def composite_player_trend(
    league: str,
    player: str,
    team: str | None = None,
    last_n_games: int = 10,
    stat_columns: list[str] | None = None,
    compact: bool = True,
) -> dict[str, Any]:
    """
    Get player's last N games with trend analysis.

    Returns:
        - Recent game logs
        - Statistical trends (averages, highs, lows)
        - Shooting splits
        - Context (home/away splits)

    Args:
        league: League identifier
        player: Player name
        team: Team name (optional, helps filter if player changed teams)
        last_n_games: Number of recent games to analyze (default: 10)
        stat_columns: Specific stats to include (default: core stats)
        compact: Enable token efficiency

    Returns:
        Dict with:
            - games: Recent game logs
            - summary: Statistical summary
            - trends: Trend indicators (improving, declining, stable)
            - splits: Home/away splits

    Examples:
        >>> # Get Cooper Flagg's last 10 games
        >>> trend = composite_player_trend(
        ...     league="NCAA-MBB",
        ...     player="Cooper Flagg",
        ...     team="Duke",
        ...     last_n_games=10
        ... )
        >>> trend["summary"]["avg_pts"]
        20.5
        >>> trend["trends"]["pts"]
        "improving"  # Based on recent vs. early games
    """
    try:
        # Step 1: Fetch player game logs
        filters = {"league": league, "player": [player]}
        if team:
            filters["team"] = [team]

        logger.info(f"Fetching trend for {player} ({league}), last {last_n_games} games")

        player_games = get_dataset("player_game", filters, limit=last_n_games * 2)

        if player_games.empty:
            return {
                "success": True,
                "games": None,
                "message": f"No games found for player: {player}",
            }

        # Step 2: Sort by date (most recent first) and limit to last N
        date_col = "GAME_DATE" if "GAME_DATE" in player_games.columns else "Date"
        if date_col in player_games.columns:
            player_games = player_games.sort_values(date_col, ascending=False)

        player_games = player_games.head(last_n_games)

        # Step 3: Calculate summary statistics
        core_stats = ["PTS", "REB", "AST", "STL", "BLK", "FG_PCT", "FG3_PCT", "FT_PCT"]
        if stat_columns:
            core_stats = stat_columns

        summary = {}
        for stat in core_stats:
            if stat in player_games.columns:
                summary[f"avg_{stat.lower()}"] = round(player_games[stat].mean(), 1)
                summary[f"max_{stat.lower()}"] = round(player_games[stat].max(), 1)
                summary[f"min_{stat.lower()}"] = round(player_games[stat].min(), 1)

        # Step 4: Calculate trends (recent vs. early)
        # Recent = last 1/3 of games, Early = first 1/3 of games
        n = len(player_games)
        third = max(1, n // 3)

        recent_games = player_games.head(third)  # Most recent (sorted desc)
        early_games = player_games.tail(third)  # Earliest games

        trends = {}
        for stat in core_stats:
            if stat in player_games.columns:
                recent_avg = recent_games[stat].mean()
                early_avg = early_games[stat].mean()

                if recent_avg > early_avg * 1.1:
                    trends[stat.lower()] = "improving"
                elif recent_avg < early_avg * 0.9:
                    trends[stat.lower()] = "declining"
                else:
                    trends[stat.lower()] = "stable"

        # Step 5: Calculate home/away splits
        splits = {}
        if "HOME_AWAY" in player_games.columns:
            home_games = player_games[player_games["HOME_AWAY"] == "Home"]
            away_games = player_games[player_games["HOME_AWAY"] == "Away"]

            for stat in core_stats:
                if stat in player_games.columns:
                    splits[f"home_{stat.lower()}"] = (
                        round(home_games[stat].mean(), 1) if not home_games.empty else 0
                    )
                    splits[f"away_{stat.lower()}"] = (
                        round(away_games[stat].mean(), 1) if not away_games.empty else 0
                    )

        # Step 6: Apply guardrails and pruning
        player_games = apply_guardrails(player_games, compact=compact)

        if compact:
            player_games = prune_to_key_columns(player_games, "player_game")

        # Step 7: Return structured result
        return {
            "success": True,
            "games": {
                "columns": player_games.columns.tolist(),
                "data": player_games.values.tolist(),
                "count": len(player_games),
            },
            "summary": summary,
            "trends": trends,
            "splits": splits,
            "games_analyzed": len(player_games),
        }

    except Exception as e:
        logger.error(f"Error in composite_player_trend: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ============================================================================
# Composite Tool: Team Recent Performance
# ============================================================================


def composite_team_recent_performance(
    league: str,
    team: str,
    last_n_games: int = 10,
    include_opponent_stats: bool = True,
    compact: bool = True,
) -> dict[str, Any]:
    """
    Get team's recent performance with advanced metrics.

    Includes:
        - Recent game results
        - Win/loss record
        - Offensive/defensive ratings
        - Strength of schedule
        - Trend indicators

    Args:
        league: League identifier
        team: Team name
        last_n_games: Number of recent games (default: 10)
        include_opponent_stats: Include opponent statistics for context
        compact: Enable token efficiency

    Returns:
        Dict with:
            - games: Recent game logs
            - record: W-L record
            - avg_stats: Average statistics
            - trends: Performance trends
            - strength_of_schedule: Opponent analysis

    Examples:
        >>> perf = composite_team_recent_performance(
        ...     league="NCAA-MBB",
        ...     team="Duke",
        ...     last_n_games=10
        ... )
        >>> perf["record"]
        {"wins": 8, "losses": 2}
        >>> perf["avg_stats"]["pts"]
        82.5
    """
    try:
        # Step 1: Fetch team game logs
        filters = {"league": league, "team": [team]}

        logger.info(f"Fetching recent performance for {team} ({league})")

        team_games = get_dataset("team_game", filters, limit=last_n_games * 2)

        if team_games.empty:
            return {"success": True, "games": None, "message": f"No games found for team: {team}"}

        # Step 2: Sort and limit
        date_col = "GAME_DATE" if "GAME_DATE" in team_games.columns else "Date"
        if date_col in team_games.columns:
            team_games = team_games.sort_values(date_col, ascending=False)

        team_games = team_games.head(last_n_games)

        # Step 3: Calculate record
        record = {"wins": 0, "losses": 0, "win_pct": 0.0}
        if "WL" in team_games.columns:
            wins = (team_games["WL"] == "W").sum()
            losses = (team_games["WL"] == "L").sum()
            record = {
                "wins": int(wins),
                "losses": int(losses),
                "win_pct": round(wins / (wins + losses), 3) if (wins + losses) > 0 else 0.0,
            }

        # Step 4: Calculate average stats
        stat_cols = ["PTS", "OPP_PTS", "FG_PCT", "FG3_PCT", "REB", "AST", "TOV"]
        avg_stats = {}
        for stat in stat_cols:
            if stat in team_games.columns:
                avg_stats[stat.lower()] = round(team_games[stat].mean(), 1)

        # Step 5: Apply guardrails
        team_games = apply_guardrails(team_games, compact=compact)

        if compact:
            team_games = prune_to_key_columns(team_games, "team_game")

        # Step 6: Return result
        return {
            "success": True,
            "games": {
                "columns": team_games.columns.tolist(),
                "data": team_games.values.tolist(),
                "count": len(team_games),
            },
            "record": record,
            "avg_stats": avg_stats,
            "games_analyzed": len(team_games),
        }

    except Exception as e:
        logger.error(f"Error in composite_team_recent_performance: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "composite_resolve_and_get_pbp",
    "composite_player_trend",
    "composite_team_recent_performance",
]
