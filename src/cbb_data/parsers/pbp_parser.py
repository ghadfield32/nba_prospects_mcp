"""Play-by-Play Parser for NCAA Basketball

Transforms ESPN play-by-play data into structured player box scores.
Solves the problem of ESPN returning empty statistics arrays for NCAA games.

Data Flow:
    ESPN API → fetch_espn_game_summary() → parse_game_to_box_score() → player box scores DataFrame

Key Functions:
    - extract_player_mapping(): Get player ID→name mapping from boxscore.players
    - parse_pbp_to_player_stats(): Calculate statistics from play-by-play events
    - parse_game_to_box_score(): Main entry point, orchestrates full transformation

"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def extract_player_mapping(boxscore: dict) -> dict:
    """Extract player ID→name mapping from ESPN boxscore.players

    ESPN's game summary API includes a 'players' array in the boxscore with complete
    team rosters including player IDs, names, jersey numbers, and positions. This
    eliminates the need for additional API calls to fetch rosters.

    Args:
        boxscore: Raw boxscore dict from ESPN API containing 'players' array

    Returns:
        Dict mapping player_id (str) → player_info (dict) with structure:
        {
            'player_id': {
                'name': str,          # Full display name
                'short_name': str,    # Abbreviated name
                'jersey': str,        # Jersey number
                'position': str,      # Position abbreviation (G, F, C)
                'team_id': str,       # Team ID
                'team_name': str      # Team display name
            },
            ...
        }

    Example:
        >>> boxscore = {'players': [{'team': {...}, 'statistics': [...]}]}
        >>> mapping = extract_player_mapping(boxscore)
        >>> mapping['5149077']['name']
        'Kingston Flemings'

    Notes:
        - Some players may not have all fields (e.g., missing jersey number)
        - Returns empty dict if boxscore.players is missing or malformed
        - Logs warning if no players found
    """
    player_map: dict[str, dict[str, Any]] = {}

    players_array = boxscore.get("players", [])
    if not players_array:
        logger.warning("No 'players' array found in boxscore")
        return player_map

    for team in players_array:
        # Extract team info
        team_data = team.get("team", {})
        team_id = team_data.get("id")
        team_name = team_data.get("displayName", "Unknown")

        # Get player statistics array (contains roster with stats)
        statistics = team.get("statistics", [])
        if not statistics or len(statistics) == 0:
            logger.warning(f"No statistics array for team {team_name}")
            continue

        # Extract athletes from first statistics group
        athletes = statistics[0].get("athletes", [])
        if not athletes:
            logger.warning(f"No athletes found for team {team_name}")
            continue

        # Process each athlete
        for athlete_data in athletes:
            athlete = athlete_data.get("athlete", {})
            player_id = athlete.get("id")

            if not player_id:
                continue  # Skip if no ID

            # Extract all available player info
            position_data = athlete.get("position", {})
            player_map[player_id] = {
                "name": athlete.get("displayName", "Unknown"),
                "short_name": athlete.get("shortName", ""),
                "jersey": athlete.get("jersey", ""),
                "position": position_data.get("abbreviation", "")
                if isinstance(position_data, dict)
                else "",
                "team_id": team_id,
                "team_name": team_name,
            }

    logger.info(
        f"Extracted player mapping for {len(player_map)} players from {len(players_array)} teams"
    )
    return player_map


def _initialize_player_stats(player_id: str) -> dict:
    """Initialize empty stats dict for a player

    Creates a dictionary with all stat categories initialized to 0. This is used
    when a player is first encountered in the play-by-play data.

    Args:
        player_id: ESPN player ID (string)

    Returns:
        Dict with all stat fields set to 0
    """
    return {
        "PLAYER_ID": player_id,
        "PTS": 0,  # Points
        "FGM": 0,  # Field goals made
        "FGA": 0,  # Field goals attempted
        "FG2M": 0,  # 2-point FG made
        "FG2A": 0,  # 2-point FG attempted
        "FG3M": 0,  # 3-point FG made
        "FG3A": 0,  # 3-point FG attempted
        "FTM": 0,  # Free throws made
        "FTA": 0,  # Free throws attempted
        "OREB": 0,  # Offensive rebounds
        "DREB": 0,  # Defensive rebounds
        "AST": 0,  # Assists
        "STL": 0,  # Steals
        "TOV": 0,  # Turnovers
        "BLK": 0,  # Blocks
        "PF": 0,  # Personal fouls
    }


def _handle_shot(
    stats: dict, shooter_id: str, participants: list, score_value: int, text: str
) -> None:
    """Process shot attempts (field goals)

    Updates shooter's stats for field goal attempts. Determines if 2PT or 3PT based
    on score_value, and if made or missed based on text keywords.

    For made shots, also checks for assists (second participant in list).

    Args:
        stats: Master stats dict {player_id: stats_dict}
        shooter_id: Player ID of shooter
        participants: List of player IDs involved [shooter, assister(optional)]
        score_value: Points scored (0=miss, 2=2PT made, 3=3PT made)
        text: Play description text (used to detect "made" vs "missed")

    Side Effects:
        Modifies stats dict in-place, updating shooter and assister stats

    Play Types Handled:
        - JumpShot (2PT or 3PT)
        - LayUpShot (2PT)
        - DunkShot (2PT)
        - TipShot (2PT)
    """
    # Determine if 2PT or 3PT from score value
    is_three = score_value == 3
    is_two = score_value == 2

    # Update attempts
    stats[shooter_id]["FGA"] += 1
    if is_three:
        stats[shooter_id]["FG3A"] += 1
    elif is_two:
        stats[shooter_id]["FG2A"] += 1

    # Check if shot was made (from text description)
    text_lower = text.lower() if text else ""
    made = "made" in text_lower or "makes" in text_lower

    if made:
        # Update makes
        stats[shooter_id]["FGM"] += 1
        if is_three:
            stats[shooter_id]["FG3M"] += 1
        elif is_two:
            stats[shooter_id]["FG2M"] += 1

        # Add points
        stats[shooter_id]["PTS"] += score_value

        # Check for assist (2nd participant)
        if len(participants) > 1:
            assister_id = participants[1]
            if assister_id not in stats:
                stats[assister_id] = _initialize_player_stats(assister_id)
            stats[assister_id]["AST"] += 1


def _handle_free_throw(stats: dict, player_id: str, play_type: str) -> None:
    """Process free throw attempts

    Updates player's FT stats. Made free throws also add 1 point.

    Args:
        stats: Master stats dict {player_id: stats_dict}
        player_id: Player ID taking free throw
        play_type: Play type string ("MadeFreeThrow" or "MissedFreeThrow")

    Side Effects:
        Modifies stats dict in-place
    """
    stats[player_id]["FTA"] += 1

    if play_type == "MadeFreeThrow":
        stats[player_id]["FTM"] += 1
        stats[player_id]["PTS"] += 1


def parse_pbp_to_player_stats(plays: pd.DataFrame, player_mapping: dict) -> pd.DataFrame:
    """Parse play-by-play events to calculate per-player statistics

    Iterates through all plays and accumulates statistics for each player based on
    play type. Uses player_mapping to enrich results with player names and team info.

    Args:
        plays: DataFrame with PBP data, required columns:
            - PLAY_TYPE: Type of play (JumpShot, MadeFreeThrow, etc.)
            - PARTICIPANTS: List of player IDs involved in play
            - SCORE_VALUE: Points scored on play (0, 1, 2, or 3)
            - TEXT: Human-readable play description
        player_mapping: Dict from extract_player_mapping() with player info

    Returns:
        DataFrame with player box scores, columns:
            - PLAYER_ID: ESPN player ID
            - PLAYER_NAME: Player's full name
            - TEAM: Team name
            - PTS, FGM, FGA, FG2M, FG2A, FG3M, FG3A, FTM, FTA
            - OREB, DREB, REB, AST, STL, TOV, BLK, PF
            - FG_PCT: Field goal percentage

    Examples:
        >>> plays = pd.DataFrame([...])  # 478 plays
        >>> mapping = extract_player_mapping(boxscore)
        >>> box_score = parse_pbp_to_player_stats(plays, mapping)
        >>> box_score[box_score['PLAYER_NAME'] == 'Kingston Flemings']['PTS'].iloc[0]
        24

    Notes:
        - Players with no stats (DNP) will not appear in output
        - Team events (team rebounds, timeouts) are skipped
        - Malformed plays are logged and skipped
        - FG_PCT = FGM / FGA, NaN becomes 0.0 for players with no attempts
    """
    if plays.empty:
        logger.warning("Empty plays DataFrame provided")
        return pd.DataFrame()

    stats = {}

    # Iterate through plays and accumulate stats
    for _, play in plays.iterrows():
        try:
            play_type = play.get("PLAY_TYPE")
            participants = play.get("PARTICIPANTS", [])
            score_value = play.get("SCORE_VALUE", 0)
            text = play.get("TEXT", "")

            # Skip team events (no participants)
            if not participants or len(participants) == 0:
                continue

            # Primary player (first in participants list)
            primary_player_id = str(participants[0])

            # Initialize player stats if first time seeing them
            if primary_player_id not in stats:
                stats[primary_player_id] = _initialize_player_stats(primary_player_id)

            # Process play based on type
            if play_type in ["JumpShot", "LayUpShot", "DunkShot", "TipShot"]:
                _handle_shot(stats, primary_player_id, participants, score_value, text)

            elif play_type in ["MadeFreeThrow", "MissedFreeThrow"]:
                _handle_free_throw(stats, primary_player_id, play_type)

            elif play_type == "Defensive Rebound":
                stats[primary_player_id]["DREB"] += 1

            elif play_type == "Offensive Rebound":
                stats[primary_player_id]["OREB"] += 1

            elif play_type == "Steal":
                stats[primary_player_id]["STL"] += 1

            elif play_type == "Block Shot":
                stats[primary_player_id]["BLK"] += 1

            elif play_type and "Turnover" in play_type:  # type: ignore[operator]
                stats[primary_player_id]["TOV"] += 1

            elif play_type == "PersonalFoul":
                stats[primary_player_id]["PF"] += 1

            # Other play types (Substitution, Timeout, etc.) don't affect box scores

        except Exception as e:
            logger.warning(f"Error processing play: {e}")
            continue

    # Convert stats dict to DataFrame
    if not stats:
        logger.warning("No player stats accumulated from plays")
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(stats, orient="index").reset_index(drop=True)

    # Enrich with player names and team info from mapping
    df["PLAYER_NAME"] = df["PLAYER_ID"].map(
        lambda pid: player_mapping.get(pid, {}).get("name", "Unknown")
    )
    df["TEAM"] = df["PLAYER_ID"].map(
        lambda pid: player_mapping.get(pid, {}).get("team_name", "Unknown")
    )

    # Calculate total rebounds
    df["REB"] = df["OREB"] + df["DREB"]

    # Calculate field goal percentage (avoid division by zero)
    df["FG_PCT"] = (df["FGM"] / df["FGA"]).fillna(0.0)

    logger.info(f"Parsed PBP to {len(df)} player box scores")
    return df


def parse_game_to_box_score(
    game_data: dict, game_id: str, season: int | None = None, league: str = "NCAA-MBB"
) -> pd.DataFrame:
    """Main entry point: Transform ESPN game data into player box scores

    Orchestrates the full PBP-to-BoxScore transformation:
    1. Extract player mapping from boxscore.players
    2. Parse plays to calculate statistics
    3. Enrich with metadata (SEASON, GAME_ID, LEAGUE)
    4. Ensure schema matches EuroLeague format

    This function solves the problem of ESPN returning empty statistics arrays
    for NCAA games by reconstructing box scores from play-by-play events.

    Args:
        game_data: Dict from fetch_espn_game_summary() with keys:
            - 'boxscore_raw': Raw boxscore dict (contains players roster)
            - 'plays': DataFrame with play-by-play data
        game_id: ESPN game ID (string)
        season: Season year (int), optional (e.g., 2025 for 2024-25 season)
        league: League identifier ("NCAA-MBB" or "NCAA-WBB")

    Returns:
        DataFrame with player box scores matching EuroLeague schema:
        - SEASON, GAME_ID, PLAYER_ID, PLAYER_NAME, TEAM, LEAGUE
        - MIN (set to "0:00" - not calculable from PBP in v1)
        - PTS, FGM, FGA, FG_PCT, FG2M, FG2A, FG3M, FG3A, FTM, FTA
        - OREB, DREB, REB, AST, STL, TOV, BLK, PF

    Example:
        >>> from cbb_data.fetchers.espn_mbb import fetch_espn_game_summary
        >>> from cbb_data.parsers.pbp_parser import parse_game_to_box_score
        >>>
        >>> game_data = fetch_espn_game_summary('401824809')
        >>> box_score = parse_game_to_box_score(game_data, '401824809', season=2026)
        >>> print(f"Generated box scores for {len(box_score)} players")
        Generated box scores for 28 players
        >>>
        >>> # Verify team totals match known score (Houston 99, Lehigh 48)
        >>> houston_pts = box_score[box_score['TEAM'] == 'Houston']['PTS'].sum()
        >>> print(f"Houston scored {houston_pts} points")
        Houston scored 99 points

    Error Handling:
        - Returns empty DataFrame if plays are empty
        - Returns empty DataFrame if player mapping fails
        - Logs warnings for missing data but continues
        - Players with 0 stats (DNP) won't appear in output

    Performance:
        - Expected time: <100ms for typical game (~400-500 plays)
        - Memory: ~50KB for 30 players with full stats
    """
    # Extract plays DataFrame
    plays = game_data.get("plays", pd.DataFrame())
    if plays.empty:
        logger.warning(f"No play-by-play data for game {game_id}")
        return pd.DataFrame()

    # Extract raw boxscore dict (contains players roster)
    boxscore_raw = game_data.get("boxscore_raw", {})
    if not boxscore_raw:
        logger.warning(f"No boxscore_raw data for game {game_id}")
        return pd.DataFrame()

    # Step 1: Extract player ID→name mapping
    player_mapping = extract_player_mapping(boxscore_raw)
    if not player_mapping:
        logger.warning(f"Failed to extract player mapping for game {game_id}")
        return pd.DataFrame()

    # Step 2: Parse plays to calculate statistics
    df = parse_pbp_to_player_stats(plays, player_mapping)
    if df.empty:
        logger.warning(f"No player stats generated from PBP for game {game_id}")
        return pd.DataFrame()

    # Step 3: Add metadata columns
    df["SEASON"] = season if season else 2026  # Default to current season
    df["GAME_ID"] = game_id
    df["LEAGUE"] = league

    # Step 4: Add columns to match EuroLeague schema
    df["MIN"] = "0:00"  # Minutes not calculable from PBP in v1
    df["Home"] = 0  # Could be derived from team_id comparison (future enhancement)
    df["STARTER"] = 0  # Could be derived from first substitutions (future enhancement)
    df["IsPlaying"] = 1  # All players in box score are playing
    df["Dorsal"] = df["PLAYER_ID"].map(lambda pid: player_mapping.get(pid, {}).get("jersey", ""))
    df["PLUS_MINUS"] = 0.0  # Not calculable from PBP alone
    df["VALUATION"] = 0  # EuroLeague-specific stat
    df["BLK_AGAINST"] = 0  # Not tracked in NCAA PBP
    df["PF_DRAWN"] = 0  # Not tracked in NCAA PBP

    # Reorder columns to match EuroLeague schema
    column_order = [
        "SEASON",
        "GAME_ID",
        "Home",
        "PLAYER_ID",
        "STARTER",
        "IsPlaying",
        "TEAM",
        "Dorsal",
        "PLAYER_NAME",
        "MIN",
        "PTS",
        "FG2M",
        "FG2A",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "STL",
        "TOV",
        "BLK",
        "BLK_AGAINST",
        "PF",
        "PF_DRAWN",
        "VALUATION",
        "PLUS_MINUS",
        "LEAGUE",
        "FGM",
        "FGA",
        "FG_PCT",
    ]

    # Ensure all columns exist (add missing ones with default values)
    for col in column_order:
        if col not in df.columns:
            df[col] = (
                0
                if col in ["Home", "STARTER", "IsPlaying", "VALUATION", "BLK_AGAINST", "PF_DRAWN"]
                else ""
            )

    # Select and reorder columns
    df = df[column_order]

    logger.info(f"Generated box score for game {game_id}: {len(df)} players")
    return df
