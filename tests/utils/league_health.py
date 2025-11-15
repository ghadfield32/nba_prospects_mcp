"""League Health Test Utilities

Centralized validation helpers for testing league fetchers.
Ensures all leagues meet quality standards for each endpoint.

Usage:
    from tests.utils.league_health import assert_schedule_ok, assert_team_game_ok

    schedule = fetcher.fetch_schedule("2023-24")
    assert_schedule_ok("LKL", "2023-24", schedule)
"""

from __future__ import annotations

# Import validation functions from contracts
import sys
from pathlib import Path

import pandas as pd

# Add src to path if running as test
src_path = Path(__file__).parent.parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from cbb_data.contracts import (  # noqa: E402
    validate_pbp,
    validate_player_game,
    validate_player_season,
    validate_schedule,
    validate_team_game,
    validate_team_season,
)

# ==============================================================================
# Schedule Validation
# ==============================================================================


def assert_schedule_ok(
    league: str,
    season: str,
    df: pd.DataFrame,
    min_games: int | None = None,
    strict: bool = False,
) -> None:
    """Assert that a schedule DataFrame meets quality standards

    Args:
        league: League identifier
        season: Season string
        df: Schedule DataFrame to validate
        min_games: Minimum expected game count (optional)
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If validation fails with detailed message

    Example:
        >>> schedule = fetcher.fetch_schedule("2023-24")
        >>> assert_schedule_ok("LKL", "2023-24", schedule, min_games=10)
    """
    # Basic validation
    assert not df.empty, f"{league} {season}: Schedule is empty"

    # Contract validation
    is_valid, issues = validate_schedule(df, league, season, strict)
    if not is_valid:
        raise AssertionError(
            f"{league} {season} schedule validation failed:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    # No duplicate GAME_IDs
    if "GAME_ID" in df.columns:
        duplicates = df[df.duplicated(subset=["GAME_ID"], keep=False)]
        assert len(duplicates) == 0, (
            f"{league} {season}: Found {len(duplicates)} duplicate GAME_IDs:\n"
            f"{duplicates[['GAME_ID', 'HOME_TEAM', 'AWAY_TEAM']].to_string()}"
        )

    # Minimum game count check
    if min_games:
        assert (
            len(df) >= min_games
        ), f"{league} {season}: Expected >= {min_games} games, got {len(df)}"

    # GAME_DATE should be valid datetime
    if "GAME_DATE" in df.columns:
        null_dates = df["GAME_DATE"].isnull().sum()
        assert null_dates == 0, f"{league} {season}: {null_dates} games have null GAME_DATE"


# ==============================================================================
# Team Game Validation
# ==============================================================================


def assert_team_game_ok(
    league: str,
    season: str,
    schedule_df: pd.DataFrame,
    team_game_df: pd.DataFrame,
    player_game_df: pd.DataFrame | None = None,
    strict: bool = False,
) -> None:
    """Assert that team_game DataFrame meets quality standards

    Args:
        league: League identifier
        season: Season string
        schedule_df: Schedule DataFrame (for cross-validation)
        team_game_df: Team game DataFrame to validate
        player_game_df: Optional player game DataFrame (for consistency checks)
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If validation fails

    Checks:
        - Basic contract validation
        - Exactly 2 teams per game (with tolerance for forfeits)
        - Team stats sum matches player stats (if player_game provided)
        - All game IDs present in schedule

    Example:
        >>> assert_team_game_ok("LKL", "2023-24", schedule, team_game, player_game)
    """
    # Basic validation
    assert not team_game_df.empty, f"{league} {season}: team_game is empty"

    # Contract validation
    is_valid, issues = validate_team_game(team_game_df, league, season, strict)
    if not is_valid:
        raise AssertionError(
            f"{league} {season} team_game validation failed:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    # Check: Exactly 2 teams per game (with some tolerance)
    if "GAME_ID" in team_game_df.columns:
        game_counts = team_game_df.groupby("GAME_ID").size()
        non_two = (game_counts != 2).sum()

        # Allow up to 5% of games to have != 2 teams (forfeits, special cases)
        total_games = len(game_counts)
        tolerance_pct = 0.05
        assert non_two <= total_games * tolerance_pct, (
            f"{league} {season}: {non_two}/{total_games} games have != 2 teams "
            f"(>{tolerance_pct * 100}% tolerance). This may indicate data quality issues."
        )

    # Check: All game IDs in team_game should be in schedule
    if "GAME_ID" in team_game_df.columns and "GAME_ID" in schedule_df.columns:
        team_game_ids = set(team_game_df["GAME_ID"].unique())
        schedule_game_ids = set(schedule_df["GAME_ID"].unique())
        missing = team_game_ids - schedule_game_ids

        assert len(missing) == 0, (
            f"{league} {season}: {len(missing)} game IDs in team_game not found in schedule: "
            f"{list(missing)[:5]}"
        )

    # Check: Team stats should roughly match sum of player stats (if provided)
    if player_game_df is not None and not player_game_df.empty:
        # Compare PTS (most reliable stat)
        if "PTS" in team_game_df.columns and "PTS" in player_game_df.columns:
            # Aggregate player points by game and team
            player_totals = (
                player_game_df.groupby(["GAME_ID", "TEAM_ID"])["PTS"].sum().reset_index()
            )

            # Join with team_game
            comparison = team_game_df.merge(
                player_totals,
                on=["GAME_ID", "TEAM_ID"],
                suffixes=("_team", "_player"),
                how="inner",
            )

            if len(comparison) > 0:
                # Check if PTS match within 5% tolerance (rounding differences)
                comparison["diff"] = abs(comparison["PTS_team"] - comparison["PTS_player"])
                comparison["diff_pct"] = (
                    comparison["diff"] / comparison["PTS_team"].replace(0, 1) * 100
                )

                mismatches = comparison[comparison["diff_pct"] > 5]
                assert len(mismatches) == 0, (
                    f"{league} {season}: {len(mismatches)} games have >5% PTS mismatch between team and player stats:\n"
                    f"{mismatches[['GAME_ID', 'TEAM_ID', 'PTS_team', 'PTS_player', 'diff_pct']].head().to_string()}"
                )


# ==============================================================================
# Player Game Validation
# ==============================================================================


def assert_player_game_ok(
    league: str,
    season: str,
    schedule_df: pd.DataFrame,
    player_game_df: pd.DataFrame,
    min_players_per_game: int = 5,
    strict: bool = False,
) -> None:
    """Assert that player_game DataFrame meets quality standards

    Args:
        league: League identifier
        season: Season string
        schedule_df: Schedule DataFrame (for cross-validation)
        player_game_df: Player game DataFrame to validate
        min_players_per_game: Minimum expected players per team per game
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If validation fails

    Example:
        >>> assert_player_game_ok("LKL", "2023-24", schedule, player_game)
    """
    # Basic validation
    assert not player_game_df.empty, f"{league} {season}: player_game is empty"

    # Contract validation
    is_valid, issues = validate_player_game(player_game_df, league, season, strict)
    if not is_valid:
        raise AssertionError(
            f"{league} {season} player_game validation failed:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    # Check: All game IDs should be in schedule
    if "GAME_ID" in player_game_df.columns and "GAME_ID" in schedule_df.columns:
        player_game_ids = set(player_game_df["GAME_ID"].unique())
        schedule_game_ids = set(schedule_df["GAME_ID"].unique())
        missing = player_game_ids - schedule_game_ids

        assert (
            len(missing) == 0
        ), f"{league} {season}: {len(missing)} game IDs in player_game not found in schedule"

    # Check: Each game should have reasonable number of players
    if "GAME_ID" in player_game_df.columns and "TEAM_ID" in player_game_df.columns:
        players_per_team_game = player_game_df.groupby(["GAME_ID", "TEAM_ID"]).size()

        # Check if any team has very few players (may indicate scraping issue)
        low_count_games = players_per_team_game[players_per_team_game < min_players_per_game]
        if len(low_count_games) > 0:
            # Warning, not error (some games might legitimately have fewer players)
            print(
                f"WARNING: {league} {season}: {len(low_count_games)} team-games have < {min_players_per_game} players"
            )


# ==============================================================================
# Play-by-Play Validation
# ==============================================================================


def assert_pbp_ok(
    league: str,
    season: str,
    schedule_df: pd.DataFrame,
    pbp_df: pd.DataFrame,
    strict: bool = False,
) -> None:
    """Assert that pbp DataFrame meets quality standards

    Args:
        league: League identifier
        season: Season string
        schedule_df: Schedule DataFrame (for cross-validation)
        pbp_df: Play-by-play DataFrame to validate
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If validation fails

    Checks:
        - Basic contract validation
        - Event numbers are sequential within each game
        - All game IDs present in schedule

    Example:
        >>> assert_pbp_ok("LKL", "2023-24", schedule, pbp)
    """
    # Basic validation
    assert not pbp_df.empty, f"{league} {season}: pbp is empty"

    # Contract validation
    is_valid, issues = validate_pbp(pbp_df, league, season, strict)
    if not is_valid:
        raise AssertionError(
            f"{league} {season} pbp validation failed:\n" + "\n".join(f"  - {i}" for i in issues)
        )

    # Check: All game IDs should be in schedule
    if "GAME_ID" in pbp_df.columns and "GAME_ID" in schedule_df.columns:
        pbp_game_ids = set(pbp_df["GAME_ID"].unique())
        schedule_game_ids = set(schedule_df["GAME_ID"].unique())
        missing = pbp_game_ids - schedule_game_ids

        assert (
            len(missing) == 0
        ), f"{league} {season}: {len(missing)} game IDs in pbp not found in schedule"

    # Check: Event numbers should be sequential (sample a few games)
    if "GAME_ID" in pbp_df.columns and "EVENT_NUM" in pbp_df.columns:
        sample_games = pbp_df["GAME_ID"].unique()[:5]  # Check first 5 games

        for game_id in sample_games:
            game_events = pbp_df[pbp_df["GAME_ID"] == game_id].sort_values("EVENT_NUM")
            event_nums = game_events["EVENT_NUM"].values

            # Check monotonic increase (allowing some gaps)
            is_increasing = all(
                event_nums[i] < event_nums[i + 1] for i in range(len(event_nums) - 1)
            )

            assert is_increasing, (
                f"{league} {season}: Game {game_id} has non-sequential EVENT_NUMs: "
                f"{event_nums[:10]}..."
            )


# ==============================================================================
# Season Aggregates Validation
# ==============================================================================


def assert_team_season_ok(
    league: str,
    season: str,
    team_season_df: pd.DataFrame,
    team_game_df: pd.DataFrame | None = None,
    strict: bool = False,
) -> None:
    """Assert that team_season DataFrame meets quality standards

    Args:
        league: League identifier
        season: Season string
        team_season_df: Team season DataFrame to validate
        team_game_df: Optional team game DataFrame (for consistency checks)
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If validation fails
    """
    # Basic validation
    assert not team_season_df.empty, f"{league} {season}: team_season is empty"

    # Contract validation
    is_valid, issues = validate_team_season(team_season_df, league, season, strict)
    if not is_valid:
        raise AssertionError(
            f"{league} {season} team_season validation failed:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    # Check: No duplicate teams
    if "TEAM_ID" in team_season_df.columns:
        duplicates = team_season_df[team_season_df.duplicated(subset=["TEAM_ID"], keep=False)]
        assert (
            len(duplicates) == 0
        ), f"{league} {season}: Found {len(duplicates)} duplicate TEAM_IDs in team_season"

    # Check: Games played should be reasonable
    if "GP" in team_season_df.columns:
        min_gp = team_season_df["GP"].min()
        max_gp = team_season_df["GP"].max()

        # Most leagues play 20-80 games per season
        assert min_gp > 0, f"{league} {season}: Some teams have 0 games played"
        assert (
            max_gp < 100
        ), f"{league} {season}: Some teams have >100 games (likely error): max={max_gp}"


def assert_player_season_ok(
    league: str,
    season: str,
    player_season_df: pd.DataFrame,
    player_game_df: pd.DataFrame | None = None,
    strict: bool = False,
) -> None:
    """Assert that player_season DataFrame meets quality standards

    Args:
        league: League identifier
        season: Season string
        player_season_df: Player season DataFrame to validate
        player_game_df: Optional player game DataFrame (for consistency checks)
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If validation fails
    """
    # Basic validation
    assert not player_season_df.empty, f"{league} {season}: player_season is empty"

    # Contract validation
    is_valid, issues = validate_player_season(player_season_df, league, season, strict)
    if not is_valid:
        raise AssertionError(
            f"{league} {season} player_season validation failed:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    # Check: No duplicate (PLAYER_ID, TEAM_ID) pairs
    if "PLAYER_ID" in player_season_df.columns and "TEAM_ID" in player_season_df.columns:
        duplicates = player_season_df[
            player_season_df.duplicated(subset=["PLAYER_ID", "TEAM_ID"], keep=False)
        ]
        assert (
            len(duplicates) == 0
        ), f"{league} {season}: Found {len(duplicates)} duplicate (PLAYER_ID, TEAM_ID) pairs in player_season"

    # Check: Games played should be reasonable
    if "GP" in player_season_df.columns:
        max_gp = player_season_df["GP"].max()
        assert (
            max_gp < 100
        ), f"{league} {season}: Some players have >100 games (likely error): max={max_gp}"


# ==============================================================================
# Composite Health Check
# ==============================================================================


def assert_league_endpoints_ok(
    league: str,
    season: str,
    endpoints: dict[str, pd.DataFrame],
    strict: bool = False,
) -> None:
    """Run all appropriate validations based on which endpoints are provided

    Args:
        league: League identifier
        season: Season string
        endpoints: Dict mapping endpoint name -> DataFrame
            Keys: "schedule", "team_game", "player_game", "pbp", "team_season", "player_season"
        strict: If True, require recommended columns too

    Raises:
        AssertionError: If any validation fails

    Example:
        >>> fetcher = LklFetcher()
        >>> endpoints = {
        ...     "schedule": fetcher.fetch_schedule("2023-24"),
        ...     "player_game": fetcher.fetch_player_game("2023-24"),
        ...     "team_game": fetcher.fetch_team_game("2023-24"),
        ...     "pbp": fetcher.fetch_pbp("2023-24"),
        ... }
        >>> assert_league_endpoints_ok("LKL", "2023-24", endpoints)
    """
    schedule = endpoints.get("schedule")
    team_game = endpoints.get("team_game")
    player_game = endpoints.get("player_game")
    pbp = endpoints.get("pbp")
    team_season = endpoints.get("team_season")
    player_season = endpoints.get("player_season")

    # Schedule is required for cross-validation
    if schedule is None or schedule.empty:
        raise AssertionError(f"{league} {season}: schedule is required but missing/empty")

    # Validate schedule
    assert_schedule_ok(league, season, schedule, strict=strict)

    # Validate other endpoints if present
    if team_game is not None and not team_game.empty:
        assert_team_game_ok(league, season, schedule, team_game, player_game, strict)

    if player_game is not None and not player_game.empty:
        assert_player_game_ok(league, season, schedule, player_game, strict=strict)

    if pbp is not None and not pbp.empty:
        assert_pbp_ok(league, season, schedule, pbp, strict=strict)

    if team_season is not None and not team_season.empty:
        assert_team_season_ok(league, season, team_season, team_game, strict)

    if player_season is not None and not player_season.empty:
        assert_player_season_ok(league, season, player_season, player_game, strict)


# ==============================================================================
# LNB API Health Check
# ==============================================================================


def health_check_lnb() -> dict[str, str]:
    """Health check for LNB API endpoints.

    Tests all 4 production LNB API endpoints:
    - get_standing (team standings)
    - get_calendar_by_division (game schedule)
    - get_competitions_by_player (player→competitions mapping)
    - get_player_performance (player stats)

    Returns:
        Dict mapping endpoint name to status ("OK" or "FAIL: <reason>")

    Example:
        >>> results = health_check_lnb()
        >>> print(results)
        {'standings': 'OK', 'calendar': 'OK', 'player_competitions': 'OK', 'player_performance': 'OK'}
    """
    from cbb_data.fetchers.lnb_api import LNBClient

    client = LNBClient()
    results = {}

    # Test 1: Standings (team season stats)
    try:
        standing = client.get_standing(competition_external_id=302)
        if "statistics" in standing and len(standing["statistics"]) > 0:
            results["standings"] = "OK"
        else:
            results["standings"] = "FAIL: Empty response"
    except Exception as e:
        results["standings"] = f"FAIL: {e}"

    # Test 2: Calendar (game schedule)
    try:
        games = client.get_calendar_by_division(division_external_id=1, year=2025)
        if len(games) > 0:
            results["calendar"] = "OK"
        else:
            results["calendar"] = "FAIL: Empty response"
    except Exception as e:
        results["calendar"] = f"FAIL: {e}"

    # Test 3: Player competitions (player→competitions mapping)
    try:
        comps = client.get_competitions_by_player(year=2025, person_external_id=3586)
        if len(comps) > 0:
            results["player_competitions"] = "OK"
        else:
            results["player_competitions"] = "FAIL: Empty response"
    except Exception as e:
        results["player_competitions"] = f"FAIL: {e}"

    # Test 4: Player performance (player season stats)
    try:
        perf = client.get_player_performance(competition_external_id=302, person_external_id=3586)
        if "person" in perf and "statData" in perf:
            results["player_performance"] = "OK"
        else:
            results["player_performance"] = "FAIL: Empty response"
    except Exception as e:
        results["player_performance"] = f"FAIL: {e}"

    return results
