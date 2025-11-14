"""Basketball Champions League (BCL) Fetcher

Official Basketball Champions League data via FIBA LiveStats JSON API and HTML scraping.

BCL is Europe's third-tier club competition (after EuroLeague and EuroCup),
organized by FIBA Europe with 32+ teams from across Europe.

⚠️ **IMPLEMENTATION NOTE**: Originally used web scraping from championsleague.basketball.
Replaced with FIBA LiveStats JSON API (primary) with HTML fallback for consistency and better data coverage.

Key Features:
- FIBA LiveStats JSON API (primary data source)
- FIBA LiveStats HTML scraping (fallback)
- Game-level data (player_game, team_game, pbp, shots)
- Season aggregate data (player_season, team_season)
- Shared infrastructure with other FIBA leagues
- Rate-limited requests with retry logic
- Local Parquet caching for performance

Data Source: FIBA LiveStats public API and HTML pages
- JSON API: https://fibalivestats.dcd.shared.geniussports.com/data/[GAME_ID]/data.json (primary)
- Box scores: https://fibalivestats.dcd.shared.geniussports.com/u/BCL/[GAME_ID]/bs.html (fallback)
- Play-by-play: https://fibalivestats.dcd.shared.geniussports.com/u/BCL/[GAME_ID]/pbp.html (fallback)

League Code: "BCL" (Basketball Champions League in FIBA LiveStats system)

Data Coverage:
- Schedule: Via pre-built game index (data/game_indexes/BCL_YYYY_YY.csv)
- Player-game box scores: Via JSON API (primary) or HTML scraping (fallback)
- Team-game box scores: Via JSON API (primary) or aggregated from player stats (fallback)
- Play-by-play: Via JSON API (primary) or HTML scraping (fallback)
- Shots: ✅ Via JSON API (includes X/Y coordinates for shot charts)
- Player-season: Aggregated from player-game
- Team-season: Aggregated from team-game

Competition Structure:
- Regular Season: 32 teams, 8 groups of 4
- Top 16: Single-elimination knockout rounds
- Final Four: Semi-finals and final
- Typical season: October-May

Historical Context:
- Founded: 2016 (replaced FIBA EuroChallenge)
- Champions: AEK Athens (2018, 2020), Virtus Bologna (2019),
  Hereda San Pablo Burgos (2021, 2022, 2023), Unicaja (2024)
- Strong European competition feeding into EuroLeague

Documentation: https://www.championsleague.basketball/
Implementation Status: ✅ IMPLEMENTED - FIBA HTML scraping (game-level + season aggregates)

Technical Notes:
- Season format: "YYYY-YY" (e.g., "2023-24" for 2023-24 season)
- Game IDs must be pre-collected (FIBA doesn't provide searchable API)
- Uses BeautifulSoup for HTML parsing
- No authentication required (public pages)
- Gracefully handles missing/incomplete data
- UTF-8 support for international player names

Dependencies:
- requests: HTTP client
- beautifulsoup4: HTML parsing
- pandas: Data manipulation
"""

from __future__ import annotations

import logging

import pandas as pd

from ..contracts import ensure_standard_columns
from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error
from .fiba_html_common import (
    load_fiba_game_index,
    scrape_fiba_box_score,
    scrape_fiba_play_by_play,
)
from .fiba_livestats_json import FibaLiveStatsClient

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# League configuration
LEAGUE = "BCL"  # Standardized league name
FIBA_LEAGUE_CODE = "BCL"  # FIBA LiveStats code
MIN_SUPPORTED_SEASON = "2016-17"

# Initialize JSON client (shared across all FIBA leagues for rate limiting)
_json_client = FibaLiveStatsClient(league_code=FIBA_LEAGUE_CODE)

# ==============================================================================
# Schedule Endpoint
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_schedule(season: str = "2023-24") -> pd.DataFrame:
    """Fetch Basketball Champions League schedule

    Loads pre-built game index from CSV file. The game index must be manually
    created since FIBA LiveStats doesn't provide a searchable schedule API.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with schedule information

    Required Columns (from game index):
        - LEAGUE: League name ("BCL")
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Final home score (optional)
        - AWAY_SCORE: Final away score (optional)
        - FIBA_COMPETITION: Competition name (e.g., "Basketball Champions League")
        - FIBA_PHASE: Phase (e.g., "RS" for Regular Season, "PO" for Playoffs)

    Example:
        >>> schedule = fetch_schedule("2023-24")
        >>> print(f"Found {len(schedule)} BCL games")
        >>> print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())

    Note:
        If game index doesn't exist, returns empty DataFrame with instructions
        for creating the index file.
    """
    df = load_fiba_game_index(FIBA_LEAGUE_CODE, season)

    if df.empty:
        logger.warning(
            f"{LEAGUE} schedule not available for {season}. "
            f"Create game index at: data/game_indexes/{FIBA_LEAGUE_CODE}_{season.replace('-', '_')}.csv"
        )
        return df

    # Ensure standard column names and metadata
    df = ensure_standard_columns(df, "schedule", LEAGUE, season)

    # Add source metadata
    df["SOURCE"] = "fiba_html"

    # Ensure team IDs (use team names as IDs for FIBA leagues)
    if "HOME_TEAM_ID" not in df.columns:
        df["HOME_TEAM_ID"] = df["HOME_TEAM"]
    if "AWAY_TEAM_ID" not in df.columns:
        df["AWAY_TEAM_ID"] = df["AWAY_TEAM"]

    return df


# ==============================================================================
# Player Game Endpoint
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_player_game(season: str = "2023-24", force_refresh: bool = False) -> pd.DataFrame:
    """Fetch Basketball Champions League player game statistics

    Uses FIBA LiveStats JSON API (primary) with HTML scraping fallback.
    Uses local caching to avoid repeated requests.

    Args:
        season: Season string (e.g., "2023-24")
        force_refresh: Force refresh cache (default: False)

    Returns:
        DataFrame with player game statistics

    Required Columns:
        - LEAGUE: "BCL"
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - PLAYER_ID: Player identifier
        - PLAYER_NAME: Player name
        - TEAM_ID: Team identifier
        - TEAM: Team name
        - MIN: Minutes played
        - PTS: Points scored
        - FGM, FGA, FG_PCT: Field goals made, attempted, percentage
        - FG3M, FG3A, FG3_PCT: Three pointers made, attempted, percentage
        - FTM, FTA, FT_PCT: Free throws made, attempted, percentage
        - OREB, DREB, REB: Offensive, defensive, total rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - SOURCE: "fiba_json" or "fiba_html"

    Example:
        >>> player_stats = fetch_player_game("2023-24")
        >>> top_scorers = player_stats.nlargest(10, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])

    Note:
        - Returns empty DataFrame if schedule not available
        - Tries JSON API first, falls back to HTML on errors
        - Uses Parquet caching for each game individually
    """
    # Get schedule first
    schedule = fetch_schedule(season)
    if schedule.empty:
        logger.warning(f"{LEAGUE} schedule not available for {season}")
        return pd.DataFrame()

    # Fetch player stats for each game
    all_player_stats = []

    for _, game_row in schedule.iterrows():
        game_id = game_row["GAME_ID"]

        try:
            # Try JSON API first
            game_data = _json_client.fetch_game_json(game_id=int(game_id))
            player_df = _json_client.to_player_game_df(game_data)

            if not player_df.empty:
                # Add game context
                player_df["GAME_ID"] = game_id
                player_df["SEASON"] = season
                player_df["LEAGUE"] = LEAGUE
                player_df["SOURCE"] = "fiba_json"

                # Generate player IDs if needed
                if "PLAYER_ID" not in player_df.columns and "TEAM" in player_df.columns:
                    player_df["PLAYER_ID"] = (
                        player_df["TEAM"].str[:3] + "_" + player_df["PLAYER_NAME"].str.replace(" ", "_")
                    )

                # Ensure team ID
                if "TEAM_ID" not in player_df.columns:
                    player_df["TEAM_ID"] = player_df["TEAM"]

                all_player_stats.append(player_df)
                logger.debug(f"Fetched {LEAGUE} game {game_id} via JSON API")
                continue

        except Exception as e:
            logger.debug(f"JSON API failed for {LEAGUE} game {game_id}, trying HTML: {e}")

        # Fallback to HTML scraping
        try:
            box_score = scrape_fiba_box_score(
                league_code=FIBA_LEAGUE_CODE,
                game_id=str(game_id),
                league=LEAGUE,
                season=season,
                force_refresh=force_refresh,
            )

            if not box_score.empty:
                # Add game identifier
                box_score["GAME_ID"] = game_id
                box_score["SOURCE"] = "fiba_html"

                # Generate player IDs (TEAM_PLAYERNAME format)
                box_score["PLAYER_ID"] = (
                    box_score["TEAM"].str[:3] + "_" + box_score["PLAYER_NAME"].str.replace(" ", "_")
                )

                # Ensure team ID
                box_score["TEAM_ID"] = box_score["TEAM"]

                all_player_stats.append(box_score)
                logger.debug(f"Fetched {LEAGUE} game {game_id} via HTML fallback")

        except Exception as e:
            logger.warning(f"Failed to fetch {LEAGUE} game {game_id} (both JSON and HTML): {e}")
            continue

    # Combine all games
    if not all_player_stats:
        logger.warning(f"No player stats fetched for {LEAGUE} {season}")
        return pd.DataFrame()

    df = pd.concat(all_player_stats, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "player_game", LEAGUE, season)

    return df


# ==============================================================================
# Team Game Endpoint
# ==============================================================================


def fetch_team_game(season: str = "2023-24") -> pd.DataFrame:
    """Fetch Basketball Champions League team game statistics

    Aggregates player game stats to team level. Each game has exactly 2 teams.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with team game statistics

    Required Columns:
        - LEAGUE: "BCL"
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - TEAM_ID: Team identifier
        - TEAM: Team name
        - MIN: Total minutes (should be 200 for regulation game)
        - PTS: Points scored
        - FGM, FGA, FG_PCT: Field goals
        - FG3M, FG3A, FG3_PCT: Three pointers
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB: Rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls

    Example:
        >>> team_stats = fetch_team_game("2023-24")
        >>> print(team_stats[["GAME_ID", "TEAM", "PTS", "REB", "AST"]].head())

    Note:
        Depends on fetch_player_game() succeeding
    """
    # Get player game stats
    player_game = fetch_player_game(season)

    if player_game.empty:
        logger.warning(f"Cannot aggregate team stats - no player data for {LEAGUE} {season}")
        return pd.DataFrame()

    # Define aggregation columns (sum all box score stats)
    agg_cols = {
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "REB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Only aggregate columns that exist
    agg_cols = {k: v for k, v in agg_cols.items() if k in player_game.columns}

    # Group by game and team
    df = player_game.groupby(["GAME_ID", "TEAM_ID", "TEAM"], as_index=False).agg(agg_cols)

    # Recalculate shooting percentages
    if "FGM" in df.columns and "FGA" in df.columns:
        df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)

    if "FG3M" in df.columns and "FG3A" in df.columns:
        df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)

    if "FTM" in df.columns and "FTA" in df.columns:
        df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

    # Add league/season metadata
    df["LEAGUE"] = LEAGUE
    df["SEASON"] = season

    return df


# ==============================================================================
# Play-by-Play Endpoint
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_pbp(season: str = "2023-24", force_refresh: bool = False) -> pd.DataFrame:
    """Fetch Basketball Champions League play-by-play data

    Uses FIBA LiveStats JSON API (primary) with HTML scraping fallback.

    Args:
        season: Season string (e.g., "2023-24")
        force_refresh: Force refresh cache (default: False)

    Returns:
        DataFrame with play-by-play events

    Required Columns:
        - LEAGUE: "BCL"
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - EVENT_NUM: Event sequence number
        - PERIOD: Period/quarter number
        - PCTIMESTRING: Game clock time
        - TEAM: Team (home/away/empty for neutral events)
        - PLAYER_NAME: Player name (if applicable)
        - ACTION_TYPE: Action description
        - DESCRIPTION: Full event description
        - SOURCE: "fiba_json" or "fiba_html"

    Example:
        >>> pbp = fetch_pbp("2023-24")
        >>> if not pbp.empty:
        >>>     print(pbp[["GAME_ID", "PERIOD", "PCTIMESTRING", "DESCRIPTION"]].head())

    Note:
        - Tries JSON API first, falls back to HTML on errors
        - Returns empty DataFrame if schedule not available
        - Skips games that fail to fetch
    """
    # Get schedule
    schedule = fetch_schedule(season)
    if schedule.empty:
        logger.warning(f"{LEAGUE} schedule not available for {season}")
        return pd.DataFrame()

    # Fetch PBP for each game
    all_pbp = []

    for _, game_row in schedule.iterrows():
        game_id = game_row["GAME_ID"]

        try:
            # Try JSON API first
            game_data = _json_client.fetch_game_json(game_id=int(game_id))
            pbp_df = _json_client.to_pbp_df(game_data)

            if not pbp_df.empty:
                # Add game context
                pbp_df["GAME_ID"] = game_id
                pbp_df["SEASON"] = season
                pbp_df["LEAGUE"] = LEAGUE
                pbp_df["SOURCE"] = "fiba_json"

                all_pbp.append(pbp_df)
                logger.debug(f"Fetched {LEAGUE} PBP for game {game_id} via JSON API")
                continue

        except Exception as e:
            logger.debug(f"JSON API failed for {LEAGUE} PBP game {game_id}, trying HTML: {e}")

        # Fallback to HTML scraping
        try:
            pbp = scrape_fiba_play_by_play(
                league_code=FIBA_LEAGUE_CODE,
                game_id=str(game_id),
                league=LEAGUE,
                season=season,
                force_refresh=force_refresh,
            )

            if not pbp.empty:
                pbp["GAME_ID"] = game_id
                pbp["SOURCE"] = "fiba_html"
                all_pbp.append(pbp)
                logger.debug(f"Fetched {LEAGUE} PBP for game {game_id} via HTML fallback")

        except Exception as e:
            logger.warning(f"Failed to fetch {LEAGUE} PBP for game {game_id} (both JSON and HTML): {e}")
            continue

    # Combine all games
    if not all_pbp:
        logger.info(f"No play-by-play data available for {LEAGUE} {season}")
        return pd.DataFrame()

    df = pd.concat(all_pbp, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "pbp", LEAGUE, season)

    return df


# ==============================================================================
# Shots Endpoint
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_shots(season: str = "2023-24", force_refresh: bool = False) -> pd.DataFrame:
    """Fetch Basketball Champions League shot data with coordinates

    Uses FIBA LiveStats JSON API to extract shot events with X/Y coordinates
    for shot chart visualization. Only available via JSON API.

    Args:
        season: Season string (e.g., "2023-24")
        force_refresh: Force refresh cache (default: False)

    Returns:
        DataFrame with shot events

    Required Columns:
        - LEAGUE: "BCL"
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - PERIOD: Period/quarter number
        - CLOCK: Game clock time
        - TEAM: Team name
        - PLAYER_NAME: Player name
        - SHOT_TYPE: "2PT" or "3PT"
        - SHOT_RESULT: "MADE" or "MISSED"
        - X: X coordinate (0-100 scale)
        - Y: Y coordinate (0-100 scale)
        - DESCRIPTION: Shot description

    Example:
        >>> shots = fetch_shots("2023-24")
        >>> made_threes = shots[(shots['SHOT_TYPE'] == '3PT') & (shots['SHOT_RESULT'] == 'MADE')]
        >>> print(f"3PT%: {len(made_threes) / len(shots[shots['SHOT_TYPE'] == '3PT']) * 100:.1f}%")

    Note:
        - Only available via JSON API (HTML doesn't provide coordinates)
        - Returns empty DataFrame if schedule not available
        - Skips games that fail to fetch
    """
    # Get schedule
    schedule = fetch_schedule(season)
    if schedule.empty:
        logger.warning(f"{LEAGUE} schedule not available for {season}")
        return pd.DataFrame()

    # Fetch shots for each game
    all_shots = []

    for _, game_row in schedule.iterrows():
        game_id = game_row["GAME_ID"]

        try:
            # Fetch from JSON API
            game_data = _json_client.fetch_game_json(game_id=int(game_id))
            shots_df = _json_client.to_shots_df(game_data)

            if not shots_df.empty:
                # Add game context
                shots_df["GAME_ID"] = game_id
                shots_df["SEASON"] = season
                shots_df["LEAGUE"] = LEAGUE
                shots_df["SOURCE"] = "fiba_json"

                all_shots.append(shots_df)
                logger.debug(f"Fetched {len(shots_df)} shots for {LEAGUE} game {game_id}")

        except Exception as e:
            logger.debug(f"Failed to fetch shots for {LEAGUE} game {game_id}: {e}")
            continue

    # Combine all games
    if not all_shots:
        logger.info(f"No shot data available for {LEAGUE} {season}")
        return pd.DataFrame()

    df = pd.concat(all_shots, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "shots", LEAGUE, season)

    logger.info(f"Fetched {len(df)} total shots for {LEAGUE} {season}")
    return df


# ==============================================================================
# Season Aggregate Endpoints
# ==============================================================================


def fetch_team_season(season: str = "2023-24") -> pd.DataFrame:
    """Fetch Basketball Champions League team season statistics

    Aggregates team game stats to season level.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with team season statistics

    Required Columns:
        - LEAGUE: "BCL"
        - SEASON: Season string
        - TEAM_ID: Team identifier
        - TEAM: Team name
        - GP: Games played
        - PTS: Total points
        - PTS_PG: Points per game
        - REB: Total rebounds
        - REB_PG: Rebounds per game
        - AST: Total assists
        - AST_PG: Assists per game
        - ... (other per-game stats)

    Example:
        >>> team_season = fetch_team_season("2023-24")
        >>> top_offense = team_season.nlargest(5, "PTS_PG")
        >>> print(top_offense[["TEAM", "GP", "PTS_PG", "REB_PG"]])
    """
    # Get team game stats
    team_game = fetch_team_game(season)

    if team_game.empty:
        logger.warning(f"Cannot aggregate team season - no game data for {LEAGUE} {season}")
        return pd.DataFrame()

    # Define aggregation (GP = count, sum everything else)
    agg_dict = {
        "GAME_ID": "count",  # Will rename to GP
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "REB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Only aggregate columns that exist
    agg_dict = {k: v for k, v in agg_dict.items() if k in team_game.columns}

    # Group by team
    df = team_game.groupby(["TEAM_ID", "TEAM"], as_index=False).agg(agg_dict)

    # Rename GAME_ID count to GP
    df.rename(columns={"GAME_ID": "GP"}, inplace=True)

    # Calculate per-game stats
    gp = df["GP"].replace(0, 1)  # Avoid division by zero

    per_game_cols = [
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "PF",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
    ]
    for col in per_game_cols:
        if col in df.columns:
            df[f"{col}_PG"] = (df[col] / gp).round(1)

    # Recalculate shooting percentages
    if "FGM" in df.columns and "FGA" in df.columns:
        df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)

    if "FG3M" in df.columns and "FG3A" in df.columns:
        df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)

    if "FTM" in df.columns and "FTA" in df.columns:
        df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

    # Add metadata
    df["LEAGUE"] = LEAGUE
    df["SEASON"] = season

    return df


def fetch_player_season(season: str = "2023-24") -> pd.DataFrame:
    """Fetch Basketball Champions League player season statistics

    Aggregates player game stats to season level.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with player season statistics

    Required Columns:
        - LEAGUE: "BCL"
        - SEASON: Season string
        - PLAYER_ID: Player identifier
        - PLAYER_NAME: Player name
        - TEAM_ID: Team identifier
        - TEAM: Team name
        - GP: Games played
        - MIN: Total minutes
        - MIN_PG: Minutes per game
        - PTS: Total points
        - PTS_PG: Points per game
        - ... (other totals and per-game stats)

    Example:
        >>> player_season = fetch_player_season("2023-24")
        >>> top_scorers = player_season.nlargest(10, "PTS_PG")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "GP", "PTS_PG", "REB_PG"]])
    """
    # Get player game stats
    player_game = fetch_player_game(season)

    if player_game.empty:
        logger.warning(f"Cannot aggregate player season - no game data for {LEAGUE} {season}")
        return pd.DataFrame()

    # Define aggregation
    agg_dict = {
        "GAME_ID": "count",  # Will rename to GP
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "REB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Only aggregate columns that exist
    agg_dict = {k: v for k, v in agg_dict.items() if k in player_game.columns}

    # Group by player
    df = player_game.groupby(["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM"], as_index=False).agg(
        agg_dict
    )

    # Rename GAME_ID count to GP
    df.rename(columns={"GAME_ID": "GP"}, inplace=True)

    # Calculate per-game stats
    gp = df["GP"].replace(0, 1)

    per_game_cols = [
        "MIN",
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "PF",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
    ]
    for col in per_game_cols:
        if col in df.columns:
            df[f"{col}_PG"] = (df[col] / gp).round(1)

    # Recalculate shooting percentages
    if "FGM" in df.columns and "FGA" in df.columns:
        df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)

    if "FG3M" in df.columns and "FG3A" in df.columns:
        df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)

    if "FTM" in df.columns and "FTA" in df.columns:
        df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

    # Add metadata
    df["LEAGUE"] = LEAGUE
    df["SEASON"] = season

    return df


# ==============================================================================
# Backwards Compatibility
# ==============================================================================

# Legacy function names (for backwards compatibility with existing code)
fetch_bcl_schedule = fetch_schedule
fetch_bcl_player_game = fetch_player_game
fetch_bcl_team_game = fetch_team_game
fetch_bcl_pbp = fetch_pbp
fetch_bcl_shots = fetch_shots
fetch_bcl_team_season = fetch_team_season
fetch_bcl_player_season = fetch_player_season
