"""LKL (Lithuania Basketball League) Fetcher

Fetches data for the Lithuanian Basketball League (LKL) via FIBA LiveStats HTML scraping.
Uses shared infrastructure from fiba_html_common.py for robust, cached scraping.

LKL is Lithuania's top-tier professional basketball league, featuring 10-12 teams.
Known for developing NBA talent including Arvydas Sabonis, Šarūnas Marčiulionis,
Žydrūnas Ilgauskas, Domantas Sabonis, and Jonas Valančiūnas.

Data Source: FIBA LiveStats HTML pages (public)
League Code: "LKL" (in FIBA system)

Data Granularities:
- schedule: ✅ Via game index CSV
- player_game: ✅ Via FIBA HTML box score scraping
- team_game: ✅ Aggregated from player_game
- pbp: ✅ Via FIBA HTML play-by-play scraping
- team_season: ✅ Aggregated from team_game
- player_season: ✅ Aggregated from player_game
- shots: ❌ FIBA HTML doesn't provide (x,y) coordinates

Competition Structure:
- Regular Season: 10-12 teams
- Playoffs: Top teams advance
- Finals: Best-of-7 series
- Season: September-May

Historical Context:
- Founded: 1993 (post-Soviet independence)
- Prominent teams: Žalgiris Kaunas, Rytas Vilnius, Lietkabelis
- EuroLeague participants: Žalgiris regularly competes in EuroLeague

Documentation: https://www.lkl.lt/
FIBA LiveStats: https://fibalivestats.dcd.shared.geniussports.com/u/LKL/
"""

from __future__ import annotations

import logging

import pandas as pd

from ..contracts import ensure_standard_columns
from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error
from .fiba_html_common import (
    build_fiba_schedule_from_html,
    load_fiba_game_index,
    scrape_fiba_box_score,
    scrape_fiba_play_by_play,
    scrape_fiba_shots,
)
from .fiba_livestats_json import FibaLiveStatsClient

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# LKL configuration
LEAGUE = "LKL"  # Standardized league name
FIBA_LEAGUE_CODE = "LKL"  # FIBA LiveStats code
MIN_SUPPORTED_SEASON = "2018-19"  # Earliest season with reliable data

# Initialize FIBA JSON client (shared across all FIBA leagues for rate limiting)
_json_client = FibaLiveStatsClient()


# ==============================================================================
# Schedule
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_schedule(season: str = "2023-24") -> pd.DataFrame:
    """Fetch LKL game schedule for a season

    **HTML-FIRST APPROACH**: Scrapes lkl.lt website to automatically
    discover game IDs and build schedule. Falls back to pre-built CSV game
    index if HTML scraping fails.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with game schedule

    Columns:
        - LEAGUE: "LKL"
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - GAME_DATE: Game date/time
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Final home score (if known)
        - AWAY_SCORE: Final away score (if known)
        - SOURCE: "schedule_html" (HTML scraping) or "game_index_csv" (fallback)

    Example:
        >>> schedule = fetch_schedule("2023-24")
        >>> print(f"Found {len(schedule)} LKL games")
        >>> print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "SOURCE"]].head())

    Note:
        - HTML scraping is attempted first (primary method)
        - If HTML fails, falls back to CSV game index
    """
    # PRIMARY: Try HTML scraping from league website
    try:
        logger.info(f"Attempting HTML-based schedule fetch for {LEAGUE} {season}")
        df = build_fiba_schedule_from_html(
            league_code=FIBA_LEAGUE_CODE,
            season=season,
            schedule_url="https://www.lkl.lt/rungtynes/",
        )

        if not df.empty:
            # Add source metadata
            df["SOURCE"] = "schedule_html"

            # Ensure team IDs (use team names as IDs for FIBA leagues)
            if "HOME_TEAM_ID" not in df.columns:
                df["HOME_TEAM_ID"] = df["HOME_TEAM"]
            if "AWAY_TEAM_ID" not in df.columns:
                df["AWAY_TEAM_ID"] = df["AWAY_TEAM"]

            logger.info(f"Successfully fetched {len(df)} games via HTML scraping")
            return df

        logger.warning("HTML scraping returned empty, falling back to CSV game index")

    except Exception as e:
        logger.warning(f"HTML scraping failed, falling back to CSV game index: {e}")

    # FALLBACK: Load from CSV game index
    logger.info(f"Loading {LEAGUE} schedule from CSV game index")
    df = load_fiba_game_index(FIBA_LEAGUE_CODE, season)

    if df.empty:
        logger.warning(
            f"{LEAGUE} schedule not available for {season}. "
            f"Create game index at: data/game_indexes/{FIBA_LEAGUE_CODE}_{season.replace('-', '_')}.csv"
        )
        return df

    # Ensure standard columns
    df = ensure_standard_columns(df, "schedule", LEAGUE, season)

    # Add metadata
    df["SOURCE"] = "game_index_csv"
    df["HOME_TEAM_ID"] = df["HOME_TEAM"]  # Use team name as ID for now
    df["AWAY_TEAM_ID"] = df["AWAY_TEAM"]

    logger.info(f"Loaded {len(df)} {LEAGUE} games for season {season}")
    return df


# ==============================================================================
# Player Game (Box Scores)
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_player_game(
    season: str = "2023-24",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch LKL player-game box scores for a season

    Scrapes FIBA LiveStats HTML pages for each game in the season.
    Uses local caching to avoid re-scraping.

    Args:
        season: Season string (e.g., "2023-24")
        force_refresh: If True, ignore cache and re-scrape all games

    Returns:
        DataFrame with player box scores

    Columns:
        - LEAGUE, SEASON, GAME_ID, TEAM_ID, TEAM, PLAYER_ID, PLAYER_NAME
        - MIN, PTS, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
        - REB, OREB, DREB, AST, STL, BLK, TOV, PF
        - SOURCE: "fiba_html"

    Example:
        >>> player_stats = fetch_player_game("2023-24")
        >>> top_scorers = player_stats.nlargest(10, 'PTS')
    """
    logger.info(f"Fetching {LEAGUE} player_game for season {season}")

    # Load schedule to get game IDs
    schedule = fetch_schedule(season)

    if schedule.empty:
        logger.warning(f"No schedule available for {LEAGUE} {season}")
        return pd.DataFrame()

    # Scrape box scores for each game
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
                # Add game context
                box_score["GAME_ID"] = game_id
                box_score["SEASON"] = season
                box_score["LEAGUE"] = LEAGUE
                box_score["SOURCE"] = "fiba_html"

                # Create player IDs (team_playerName for uniqueness)
                if "TEAM" in box_score.columns and "PLAYER_NAME" in box_score.columns:
                    box_score["PLAYER_ID"] = (
                        box_score["TEAM"].str[:3]
                        + "_"
                        + box_score["PLAYER_NAME"].str.replace(" ", "_")
                    )
                    box_score["TEAM_ID"] = box_score["TEAM"]  # Use team name as ID

                all_player_stats.append(box_score)
                logger.debug(f"Fetched {LEAGUE} game {game_id} via HTML fallback")

        except Exception as e:
            logger.warning(f"Failed to fetch {LEAGUE} game {game_id} (both JSON and HTML): {e}")
            continue

    if not all_player_stats:
        logger.warning(f"No player stats fetched for {LEAGUE} {season}")
        return pd.DataFrame()

    # Concatenate all games
    df = pd.concat(all_player_stats, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "player_game", LEAGUE, season)

    logger.info(f"Scraped {len(df)} player-game records for {LEAGUE} {season}")
    return df


# ==============================================================================
# Team Game (Aggregated from Player Game)
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_team_game(season: str = "2023-24") -> pd.DataFrame:
    """Fetch LKL team-game box scores (aggregated from player stats)

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with team box scores

    Columns:
        - LEAGUE, SEASON, GAME_ID, TEAM_ID, TEAM
        - MIN, PTS, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
        - REB, OREB, DREB, AST, STL, BLK, TOV, PF
        - SOURCE: "fiba_html_aggregated"

    Example:
        >>> team_stats = fetch_team_game("2023-24")
        >>> high_scoring = team_stats.nlargest(10, 'PTS')
    """
    logger.info(f"Fetching {LEAGUE} team_game for season {season}")

    # Get player-game stats
    player_game = fetch_player_game(season)

    if player_game.empty:
        logger.warning(f"No player_game data available for {LEAGUE} {season}")
        return pd.DataFrame()

    # Aggregate by game and team
    agg_cols = {
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "REB": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Only aggregate columns that exist
    agg_cols = {k: v for k, v in agg_cols.items() if k in player_game.columns}

    df = player_game.groupby(["GAME_ID", "TEAM_ID", "TEAM"], as_index=False).agg(agg_cols)

    # Recalculate percentages
    if "FGM" in df.columns and "FGA" in df.columns:
        df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)
    if "FG3M" in df.columns and "FG3A" in df.columns:
        df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)
    if "FTM" in df.columns and "FTA" in df.columns:
        df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

    # Add standard columns
    df["LEAGUE"] = LEAGUE
    df["SEASON"] = season
    df = ensure_standard_columns(df, "team_game", LEAGUE, season)
    df["SOURCE"] = "fiba_html_aggregated"

    logger.info(f"Aggregated {len(df)} team-game records for {LEAGUE} {season}")
    return df


# ==============================================================================
# Play-by-Play
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_pbp(
    season: str = "2023-24",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch LKL play-by-play events for a season

    Scrapes FIBA LiveStats HTML pages for each game.
    Uses local caching to avoid re-scraping.

    Args:
        season: Season string (e.g., "2023-24")
        force_refresh: If True, ignore cache and re-scrape all games

    Returns:
        DataFrame with play-by-play events

    Columns:
        - LEAGUE, SEASON, GAME_ID, EVENT_NUM, PERIOD, CLOCK
        - TEAM, PLAYER, EVENT_TYPE, DESCRIPTION
        - SCORE_HOME, SCORE_AWAY
        - SOURCE: "fiba_html"

    Example:
        >>> pbp = fetch_pbp("2023-24")
        >>> three_pointers = pbp[pbp['EVENT_TYPE'] == '3PT_SHOT']
    """
    logger.info(f"Fetching {LEAGUE} pbp for season {season}")

    # Load schedule to get game IDs
    schedule = fetch_schedule(season)

    if schedule.empty:
        logger.warning(f"No schedule available for {LEAGUE} {season}")
        return pd.DataFrame()

    # Scrape PBP for each game
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

    if not all_pbp:
        logger.warning(f"No PBP events scraped for {LEAGUE} {season}")
        return pd.DataFrame()

    # Concatenate all games
    df = pd.concat(all_pbp, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "pbp", LEAGUE, season)

    logger.info(f"Scraped {len(df)} PBP events for {LEAGUE} {season}")
    return df


# ==============================================================================
# Shots
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_shots(season: str = "2023-24", force_refresh: bool = False) -> pd.DataFrame:
    """Fetch LKL shot data with coordinates

    **DUAL-SOURCE APPROACH**: Uses FIBA LiveStats JSON API (primary) with HTML
    scraping fallback. HTML scraping can extract shot coordinates from embedded
    JSON or HTML elements on FIBA LiveStats pages.

    Args:
        season: Season string (e.g., "2023-24")
        force_refresh: Force refresh cache (default: False)

    Returns:
        DataFrame with shot events

    Required Columns:
        - LEAGUE: "LKL"
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
        - SOURCE: "fiba_json" (JSON API) or "fiba_html" (HTML scraping)

    Example:
        >>> shots = fetch_shots("2023-24")
        >>> made_threes = shots[(shots['SHOT_TYPE'] == '3PT') & (shots['SHOT_RESULT'] == 'MADE')]
        >>> print(f"3PT%: {len(made_threes) / len(shots[shots['SHOT_TYPE'] == '3PT']) * 100:.1f}%")

    Note:
        - Tries JSON API first, falls back to HTML on errors
        - Returns empty DataFrame if schedule not available
        - Skips games that fail to fetch from both sources
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

        # PRIMARY: Try JSON API first
        try:
            game_data = _json_client.fetch_game_json(game_id=int(game_id))
            shots_df = _json_client.to_shots_df(game_data)

            if not shots_df.empty:
                # Add game context
                shots_df["GAME_ID"] = game_id
                shots_df["SEASON"] = season
                shots_df["LEAGUE"] = LEAGUE
                shots_df["SOURCE"] = "fiba_json"

                all_shots.append(shots_df)
                logger.debug(f"Fetched {len(shots_df)} shots for {LEAGUE} game {game_id} via JSON")
                continue

        except Exception as e:
            logger.debug(f"JSON API failed for {LEAGUE} shots game {game_id}, trying HTML: {e}")

        # FALLBACK: Try HTML scraping
        try:
            shots_df = scrape_fiba_shots(
                league_code=FIBA_LEAGUE_CODE,
                game_id=game_id,
                league=LEAGUE,
                season=season,
                force_refresh=force_refresh,
            )

            if not shots_df.empty:
                shots_df["SOURCE"] = "fiba_html"
                all_shots.append(shots_df)
                logger.debug(f"Fetched {len(shots_df)} shots for {LEAGUE} game {game_id} via HTML")

        except Exception as e:
            logger.debug(f"Failed to fetch shots for {LEAGUE} game {game_id} (both JSON and HTML): {e}")
            continue

    # Combine all games
    if not all_shots:
        logger.info(f"No shot data available for {LEAGUE} {season}")
        return pd.DataFrame()

    df = pd.concat(all_shots, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "shots", LEAGUE, season)

    logger.info(f"Fetched {len(df)} shot events for {LEAGUE} {season}")
    return df


# ==============================================================================
# Season Aggregates
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_team_season(season: str = "2023-24") -> pd.DataFrame:
    """Fetch LKL team season aggregates (from team_game)

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with team season statistics

    Columns:
        - LEAGUE, SEASON, TEAM_ID, TEAM
        - GP: Games played
        - MIN, PTS, FGM, FGA, FG_PCT, etc.
        - PTS_PG: Points per game
        - REB_PG: Rebounds per game
        - AST_PG: Assists per game

    Example:
        >>> team_season = fetch_team_season("2023-24")
        >>> standings = team_season.nlargest(10, 'PTS_PG')
    """
    logger.info(f"Fetching {LEAGUE} team_season for season {season}")

    # Get team-game stats
    team_game = fetch_team_game(season)

    if team_game.empty:
        logger.warning(f"No team_game data available for {LEAGUE} {season}")
        return pd.DataFrame()

    # Aggregate by team
    agg_dict = {
        "GAME_ID": "count",  # Games played
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "REB": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Only aggregate columns that exist
    agg_dict = {k: v for k, v in agg_dict.items() if k in team_game.columns or k == "GAME_ID"}

    df = team_game.groupby(["TEAM_ID", "TEAM"], as_index=False).agg(agg_dict)

    # Rename GAME_ID count to GP
    df.rename(columns={"GAME_ID": "GP"}, inplace=True)

    # Calculate per-game stats
    gp = df["GP"].replace(0, 1)  # Avoid division by zero
    if "PTS" in df.columns:
        df["PTS_PG"] = (df["PTS"] / gp).round(1)
    if "REB" in df.columns:
        df["REB_PG"] = (df["REB"] / gp).round(1)
    if "AST" in df.columns:
        df["AST_PG"] = (df["AST"] / gp).round(1)

    # Recalculate percentages
    if "FGM" in df.columns and "FGA" in df.columns:
        df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)
    if "FG3M" in df.columns and "FG3A" in df.columns:
        df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)
    if "FTM" in df.columns and "FTA" in df.columns:
        df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

    # Add standard columns
    df["LEAGUE"] = LEAGUE
    df["SEASON"] = season
    df = ensure_standard_columns(df, "team_season", LEAGUE, season)

    logger.info(f"Aggregated {len(df)} teams for {LEAGUE} {season}")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_player_season(season: str = "2023-24") -> pd.DataFrame:
    """Fetch LKL player season aggregates (from player_game)

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with player season statistics

    Columns:
        - LEAGUE, SEASON, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM
        - GP: Games played
        - MIN, PTS, FGM, FGA, FG_PCT, etc.
        - PTS_PG: Points per game
        - REB_PG: Rebounds per game
        - AST_PG: Assists per game

    Example:
        >>> player_season = fetch_player_season("2023-24")
        >>> top_scorers = player_season.nlargest(10, 'PTS_PG')
    """
    logger.info(f"Fetching {LEAGUE} player_season for season {season}")

    # Get player-game stats
    player_game = fetch_player_game(season)

    if player_game.empty:
        logger.warning(f"No player_game data available for {LEAGUE} {season}")
        return pd.DataFrame()

    # Aggregate by player
    agg_dict = {
        "GAME_ID": "count",  # Games played
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "REB": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Only aggregate columns that exist
    agg_dict = {k: v for k, v in agg_dict.items() if k in player_game.columns or k == "GAME_ID"}

    df = player_game.groupby(["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM"], as_index=False).agg(
        agg_dict
    )

    # Rename GAME_ID count to GP
    df.rename(columns={"GAME_ID": "GP"}, inplace=True)

    # Calculate per-game stats
    gp = df["GP"].replace(0, 1)  # Avoid division by zero
    if "PTS" in df.columns:
        df["PTS_PG"] = (df["PTS"] / gp).round(1)
    if "MIN" in df.columns:
        df["MIN_PG"] = (df["MIN"] / gp).round(1)
    if "REB" in df.columns:
        df["REB_PG"] = (df["REB"] / gp).round(1)
    if "AST" in df.columns:
        df["AST_PG"] = (df["AST"] / gp).round(1)

    # Recalculate percentages
    if "FGM" in df.columns and "FGA" in df.columns:
        df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)
    if "FG3M" in df.columns and "FG3A" in df.columns:
        df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)
    if "FTM" in df.columns and "FTA" in df.columns:
        df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

    # Add standard columns
    df["LEAGUE"] = LEAGUE
    df["SEASON"] = season
    df = ensure_standard_columns(df, "player_season", LEAGUE, season)

    logger.info(f"Aggregated {len(df)} players for {LEAGUE} {season}")
    return df


# ==============================================================================
# Backwards Compatibility (Old Function Names)
# ==============================================================================


def fetch_lkl_schedule(season: str = "2023-24") -> pd.DataFrame:
    """Backwards compatibility wrapper for fetch_schedule"""
    return fetch_schedule(season)


def fetch_lkl_player_game(season: str = "2023-24") -> pd.DataFrame:
    """Backwards compatibility wrapper for fetch_player_game"""
    return fetch_player_game(season)


def fetch_lkl_team_game(season: str = "2023-24") -> pd.DataFrame:
    """Backwards compatibility wrapper for fetch_team_game"""
    return fetch_team_game(season)


def fetch_lkl_pbp(season: str = "2023-24") -> pd.DataFrame:
    """Backwards compatibility wrapper for fetch_pbp"""
    return fetch_pbp(season)


def fetch_lkl_player_season(season: str = "2023-24") -> pd.DataFrame:
    """Backwards compatibility wrapper for fetch_player_season"""
    return fetch_player_season(season)


def fetch_lkl_team_season(season: str = "2023-24") -> pd.DataFrame:
    """Backwards compatibility wrapper for fetch_team_season"""
    return fetch_team_season(season)
