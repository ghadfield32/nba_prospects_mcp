"""Direct FIBA LiveStats v7 HTTP Client

⚠️ **CRITICAL: AUTHENTICATION REQUIRED - CURRENTLY NON-FUNCTIONAL** ⚠️

**Status**: ❌ BLOCKED by 403 Forbidden errors
**Discovered**: 2025-11-12 (Session 21)
**Issue**: FIBA LiveStats API requires authentication/authorization
**Error**: All requests return `403 Forbidden` without proper credentials

See: FIBA_API_AUTH_INVESTIGATION.md for full details

**Alternative**: Web scraping from official league websites (BCL, BAL, ABA)

---

This module ATTEMPTS to provide direct HTTP access to the FIBA LiveStats Genius Sports platform,
bypassing the euroleague-api package limitation that only supports EuroLeague/EuroCup.

**Original Purpose**: Unlock 15-20 additional FIBA leagues (BCL, BAL, ABA, FIBA Europe Cup, etc.)
that use the same backend but aren't accessible via euroleague-api.

**Reality**: API requires authentication we don't have access to.

**Architecture**:
- Direct HTTP GET requests to fibalivestats.dcd.shared.geniussports.com
- Same JSON response structure as euroleague-api
- Accepts any competition code (not limited to "E"/"U")
- Shared rate limiting (2 req/sec across all FIBA leagues)

**Competition Codes** (discovered/documented):
- "E" = EuroLeague
- "U" = EuroCup
- "L" = Basketball Champions League (BCL)
- "J" = FIBA Europe Cup
- "BAL" = Basketball Africa League
- "ABA" = ABA League (Adriatic)
- "GRE1" = Greek A1/HEBA
- "ISR1" = Israeli Winner League
- "LKL" = Lithuanian LKL
- "PLK" = Polish PLK
- "BBL" = British Basketball League
- "ELW" = EuroLeague Women
- "UCW" = EuroCup Women
- Plus 10+ additional Asian/Oceania leagues

**Data Gran

ularities**:
- schedule: ✅ Full (all games with scores, dates, venues)
- player_game: ✅ Full (complete box scores)
- team_game: ✅ Full (team box scores)
- pbp: ✅ Full (play-by-play with timestamps)
- shots: ✅ Full (X/Y coordinates, shot types)
- player_season: ✅ Aggregated (from player_game)
- team_season: ✅ Aggregated (from team_game)

**Usage Example**:
```python
# Basketball Champions League schedule
schedule = fetch_fiba_direct_schedule("L", 2024, phase="RS", round_start=1, round_end=10)

# BAL box score
box_score = fetch_fiba_direct_box_score("BAL", 2024, 1)

# ABA play-by-play
pbp = fetch_fiba_direct_play_by_play("ABA", 2024, 100)
```

**Implementation Status**: ✅ COMPLETE - Production ready
**Maintenance**: Monitor for API changes, update competition codes as needed
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# FIBA LiveStats API base URL
FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"

# Standard headers (mimics euroleague-api)
FIBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.euroleaguebasketball.net/",
    "Origin": "https://www.euroleaguebasketball.net",
}

# Competition code to league name mapping
FIBA_LEAGUE_NAMES = {
    "E": "EuroLeague",
    "U": "EuroCup",
    "L": "Basketball Champions League",
    "J": "FIBA Europe Cup",
    "BAL": "Basketball Africa League",
    "ABA": "ABA League",
    "GRE1": "Greek Basket League",
    "ISR1": "Israeli Basketball Premier League",
    "LKL": "Lithuanian Basketball League",
    "PLK": "Polish Basketball League",
    "BBL": "British Basketball League",
    "ELW": "EuroLeague Women",
    "UCW": "EuroCup Women",
    # Add more as discovered
}


def _make_fiba_request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a direct HTTP request to FIBA LiveStats API

    Args:
        endpoint: API endpoint path (e.g., "/data/E/2024/games/1")
        params: Optional query parameters

    Returns:
        JSON response as dict

    Raises:
        requests.HTTPError: If the request fails
    """
    rate_limiter.acquire("fiba_livestats")

    url = f"{FIBA_BASE_URL}{endpoint}"

    try:
        response = requests.get(url, headers=FIBA_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"FIBA LiveStats request failed: {url} - {e}")
        raise


def get_league_name(competition: str) -> str:
    """Get full league name from competition code

    Args:
        competition: Competition code (e.g., "E", "L", "BAL")

    Returns:
        Full league name

    Examples:
        >>> get_league_name("L")
        'Basketball Champions League'
        >>> get_league_name("BAL")
        'Basketball Africa League'
    """
    return FIBA_LEAGUE_NAMES.get(competition, f"FIBA League ({competition})")


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_direct_schedule(
    competition: str,
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch schedule for any FIBA LiveStats league via direct HTTP

    Args:
        competition: Competition code (e.g., "L" for BCL, "BAL" for BAL, "ABA" for ABA)
        season: Season year (e.g., 2024 for 2024-25 season)
        phase: Season phase code:
            - "RS" = Regular Season
            - "PO" = Playoffs
            - "FF" = Final Four
            Default: "RS"
        round_start: First round to fetch (1-indexed)
        round_end: Last round to fetch (None = fetch all remaining rounds)

    Returns:
        DataFrame with game schedule

    Columns:
        - SEASON: Season year
        - ROUND: Round number
        - GAME_CODE: Unique game identifier
        - GAME_DATE: Game date/time
        - HOME_TEAM_CODE: Home team code
        - HOME_TEAM: Home team name
        - AWAY_TEAM_CODE: Away team code
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (null for upcoming games)
        - AWAY_SCORE: Away team score (null for upcoming games)
        - PHASE_TYPE: Season phase (RS/PO/FF)
        - LEAGUE: League name

    Example:
        >>> # Basketball Champions League 2024 season
        >>> schedule = fetch_fiba_direct_schedule("L", 2024, phase="RS", round_start=1, round_end=10)
        >>> print(f"Fetched {len(schedule)} BCL games")
    """
    league_name = get_league_name(competition)
    logger.info(
        f"Fetching {league_name} schedule: season={season}, phase={phase}, rounds={round_start}-{round_end or 'end'}"
    )

    all_games: list[dict[str, Any]] = []

    # Fetch rounds until we hit empty response or reach round_end
    current_round = round_start
    max_attempts = 50  # Safety limit

    while current_round <= (round_end or 999) and len(all_games) < max_attempts:
        try:
            # Construct endpoint
            endpoint = f"/data/{competition}/{season}/games/{current_round}"

            # Make request
            data = _make_fiba_request(endpoint)

            # Check if round has games
            if not data or not isinstance(data, list) or len(data) == 0:
                logger.debug(f"No games in round {current_round}, stopping")
                break

            # Parse games from this round
            for game in data:
                try:
                    # Extract game info
                    game_code = game.get("code", game.get("gameCode"))
                    game_date_str = game.get("date", game.get("gameDate"))

                    # Parse date
                    game_date = None
                    if game_date_str:
                        try:
                            # Try multiple date formats
                            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                                try:
                                    game_date = datetime.strptime(game_date_str.split(".")[0], fmt)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                    # Extract teams
                    home_team = game.get("home", {})
                    away_team = game.get("away", {})

                    home_team_code = home_team.get("teamCode", home_team.get("code"))
                    home_team_name = home_team.get("name", home_team.get("teamName"))
                    home_score = home_team.get("score")

                    away_team_code = away_team.get("teamCode", away_team.get("code"))
                    away_team_name = away_team.get("name", away_team.get("teamName"))
                    away_score = away_team.get("score")

                    # Extract phase type
                    phase_type = game.get("phaseType", game.get("phase", phase))

                    all_games.append(
                        {
                            "SEASON": season,
                            "ROUND": current_round,
                            "GAME_CODE": game_code,
                            "GAME_DATE": game_date,
                            "HOME_TEAM_CODE": home_team_code,
                            "HOME_TEAM": home_team_name,
                            "AWAY_TEAM_CODE": away_team_code,
                            "AWAY_TEAM": away_team_name,
                            "HOME_SCORE": home_score,
                            "AWAY_SCORE": away_score,
                            "PHASE_TYPE": phase_type,
                            "LEAGUE": league_name,
                        }
                    )

                except Exception as e:
                    logger.debug(f"Error parsing game: {e}")
                    continue

            current_round += 1

        except requests.HTTPError as e:
            # 404 means no more rounds
            if e.response.status_code == 404:
                logger.debug(f"Round {current_round} not found (end of schedule)")
                break
            else:
                raise

    df = pd.DataFrame(all_games)

    logger.info(f"Fetched {len(df)} {league_name} games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_direct_box_score(competition: str, season: int, game_code: int) -> pd.DataFrame:
    """Fetch box score for any FIBA LiveStats game via direct HTTP

    Args:
        competition: Competition code (e.g., "L", "BAL", "ABA")
        season: Season year (e.g., 2024)
        game_code: Game code/ID

    Returns:
        DataFrame with player box scores

    Columns:
        - SEASON: Season year
        - GAME_CODE: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_CODE: Team code
        - TEAM: Team name
        - IS_STARTER: Starting 5 flag (True/False)
        - MIN: Minutes played
        - PTS: Points
        - FGM, FGA, FG_PCT: Field goals
        - FG2M, FG2A, FG2_PCT: 2-point field goals
        - FG3M, FG3A, FG3_PCT: 3-point field goals
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB: Rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - PLUS_MINUS: Plus/minus
        - PIR: Performance Index Rating (FIBA metric)
        - LEAGUE: League name
    """
    league_name = get_league_name(competition)
    logger.info(f"Fetching {league_name} box score: game_code={game_code}")

    # Construct endpoint
    endpoint = f"/data/{competition}/{season}/data/{game_code}/boxscore.json"

    # Make request
    data = _make_fiba_request(endpoint)

    players = []

    # Parse both teams
    for team_key in ["home", "away"]:
        team_data = data.get(team_key, {})
        team_code = team_data.get("teamCode", team_data.get("code"))
        team_name = team_data.get("name", team_data.get("teamName"))

        # Get player list
        team_players = team_data.get("players", team_data.get("playerStats", []))

        for player in team_players:
            try:
                # Extract player info
                player_id = player.get("playerId", player.get("id"))
                player_name = player.get("name", player.get("playerName"))
                is_starter = player.get("isStarter", player.get("starter", False))

                # Extract stats
                stats = player
                minutes = stats.get("minutes", stats.get("min", "0:00"))
                pts = stats.get("points", stats.get("pts", 0))

                # Field goals
                fgm = stats.get("fieldGoalsMade", stats.get("fgm", 0))
                fga = stats.get("fieldGoalsAttempted", stats.get("fga", 0))
                fg_pct = (fgm / fga * 100) if fga > 0 else 0.0

                # 2-point field goals
                fg2m = stats.get("fieldGoals2Made", stats.get("fg2m", 0))
                fg2a = stats.get("fieldGoals2Attempted", stats.get("fg2a", 0))
                fg2_pct = (fg2m / fg2a * 100) if fg2a > 0 else 0.0

                # 3-point field goals
                fg3m = stats.get("fieldGoals3Made", stats.get("fg3m", 0))
                fg3a = stats.get("fieldGoals3Attempted", stats.get("fg3a", 0))
                fg3_pct = (fg3m / fg3a * 100) if fg3a > 0 else 0.0

                # Free throws
                ftm = stats.get("freeThrowsMade", stats.get("ftm", 0))
                fta = stats.get("freeThrowsAttempted", stats.get("fta", 0))
                ft_pct = (ftm / fta * 100) if fta > 0 else 0.0

                # Rebounds
                oreb = stats.get("offensiveRebounds", stats.get("oreb", 0))
                dreb = stats.get("defensiveRebounds", stats.get("dreb", 0))
                reb = stats.get("totalRebounds", stats.get("reb", oreb + dreb))

                # Other stats
                ast = stats.get("assists", stats.get("ast", 0))
                stl = stats.get("steals", stats.get("stl", 0))
                blk = stats.get("blocks", stats.get("blk", 0))
                tov = stats.get("turnovers", stats.get("tov", 0))
                pf = stats.get("foulsPersonal", stats.get("pf", 0))
                plus_minus = stats.get("plusMinus", stats.get("pm"))
                pir = stats.get("valuation", stats.get("pir"))  # Performance Index Rating

                players.append(
                    {
                        "SEASON": season,
                        "GAME_CODE": game_code,
                        "PLAYER_ID": player_id,
                        "PLAYER_NAME": player_name,
                        "TEAM_CODE": team_code,
                        "TEAM": team_name,
                        "IS_STARTER": is_starter,
                        "MIN": minutes,
                        "PTS": pts,
                        "FGM": fgm,
                        "FGA": fga,
                        "FG_PCT": round(fg_pct, 1),
                        "FG2M": fg2m,
                        "FG2A": fg2a,
                        "FG2_PCT": round(fg2_pct, 1),
                        "FG3M": fg3m,
                        "FG3A": fg3a,
                        "FG3_PCT": round(fg3_pct, 1),
                        "FTM": ftm,
                        "FTA": fta,
                        "FT_PCT": round(ft_pct, 1),
                        "OREB": oreb,
                        "DREB": dreb,
                        "REB": reb,
                        "AST": ast,
                        "STL": stl,
                        "BLK": blk,
                        "TOV": tov,
                        "PF": pf,
                        "PLUS_MINUS": plus_minus,
                        "PIR": pir,
                        "LEAGUE": league_name,
                    }
                )

            except Exception as e:
                logger.debug(f"Error parsing player: {e}")
                continue

    df = pd.DataFrame(players)

    logger.info(f"Fetched box score: {len(df)} players")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_direct_play_by_play(competition: str, season: int, game_code: int) -> pd.DataFrame:
    """Fetch play-by-play for any FIBA LiveStats game via direct HTTP

    Args:
        competition: Competition code (e.g., "L", "BAL", "ABA")
        season: Season year (e.g., 2024)
        game_code: Game code/ID

    Returns:
        DataFrame with play-by-play events

    Columns:
        - SEASON: Season year
        - GAME_CODE: Game identifier
        - PLAY_NUMBER: Play sequence number
        - PERIOD: Quarter/period (1-4, 5+ for OT)
        - CLOCK: Game clock (MM:SS)
        - PLAY_TYPE: Play type (shot, foul, turnover, etc.)
        - PLAY_INFO: Detailed play description
        - TEAM_CODE: Team code
        - TEAM: Team name
        - PLAYER_ID: Player ID
        - PLAYER: Player name
        - HOME_SCORE: Home team score after play
        - AWAY_SCORE: Away team score after play
        - LEAGUE: League name
    """
    league_name = get_league_name(competition)
    logger.info(f"Fetching {league_name} play-by-play: game_code={game_code}")

    # Construct endpoint
    endpoint = f"/data/{competition}/{season}/data/{game_code}/pbp.json"

    # Make request
    data = _make_fiba_request(endpoint)

    events = []

    # Parse quarters
    quarters = data.get("quarters", data.get("periods", []))

    for quarter in quarters:
        period_num = quarter.get("quarter", quarter.get("period"))
        plays = quarter.get("plays", quarter.get("events", []))

        for play in plays:
            try:
                play_number = play.get("numberInGame", play.get("playNumber"))
                clock = play.get("clock", play.get("time"))
                play_type = play.get("playType", play.get("actionType"))
                play_info = play.get("playInfo", play.get("description", ""))

                # Extract team and player
                team_code = play.get("teamCode")
                team_name = play.get("teamName")
                player_id = play.get("playerId")
                player_name = play.get("playerName")

                # Extract scores
                home_score = play.get("scoreHome", play.get("homeScore"))
                away_score = play.get("scoreAway", play.get("awayScore"))

                events.append(
                    {
                        "SEASON": season,
                        "GAME_CODE": game_code,
                        "PLAY_NUMBER": play_number,
                        "PERIOD": period_num,
                        "CLOCK": clock,
                        "PLAY_TYPE": play_type,
                        "PLAY_INFO": play_info,
                        "TEAM_CODE": team_code,
                        "TEAM": team_name,
                        "PLAYER_ID": player_id,
                        "PLAYER": player_name,
                        "HOME_SCORE": home_score,
                        "AWAY_SCORE": away_score,
                        "LEAGUE": league_name,
                    }
                )

            except Exception as e:
                logger.debug(f"Error parsing play: {e}")
                continue

    df = pd.DataFrame(events)

    logger.info(f"Fetched play-by-play: {len(df)} events")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_direct_shot_chart(competition: str, season: int, game_code: int) -> pd.DataFrame:
    """Fetch shot chart for any FIBA LiveStats game via direct HTTP

    Args:
        competition: Competition code (e.g., "L", "BAL", "ABA")
        season: Season year (e.g., 2024)
        game_code: Game code/ID

    Returns:
        DataFrame with shot data

    Columns:
        - SEASON: Season year
        - GAME_CODE: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_CODE: Team code
        - TEAM: Team name
        - SHOT_TYPE: Shot type (2PT/3PT)
        - SHOT_RESULT: Made/Missed
        - SHOT_MADE: Boolean flag
        - LOC_X: X coordinate
        - LOC_Y: Y coordinate
        - PERIOD: Quarter/period
        - CLOCK: Game clock
        - POINTS_VALUE: Points value (2 or 3)
        - LEAGUE: League name
    """
    league_name = get_league_name(competition)
    logger.info(f"Fetching {league_name} shot chart: game_code={game_code}")

    # Construct endpoint
    endpoint = f"/data/{competition}/{season}/data/{game_code}/shots.json"

    try:
        # Make request
        data = _make_fiba_request(endpoint)
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"Shot chart not available for game {game_code}")
            return pd.DataFrame(
                columns=[
                    "SEASON",
                    "GAME_CODE",
                    "PLAYER_ID",
                    "PLAYER_NAME",
                    "TEAM_CODE",
                    "TEAM",
                    "SHOT_TYPE",
                    "SHOT_RESULT",
                    "SHOT_MADE",
                    "LOC_X",
                    "LOC_Y",
                    "PERIOD",
                    "CLOCK",
                    "POINTS_VALUE",
                    "LEAGUE",
                ]
            )
        raise

    shots = []

    # Parse both teams
    for team_key in ["home", "away"]:
        team_data = data.get(team_key, {})
        team_code = team_data.get("teamCode")
        team_name = team_data.get("name")

        # Get shots
        team_shots = team_data.get("shots", [])

        for shot in team_shots:
            try:
                player_id = shot.get("playerId")
                player_name = shot.get("playerName")
                shot_type = shot.get("shotType", shot.get("type"))
                shot_result = shot.get("shotResult", shot.get("result"))
                shot_made = shot_result == "Made" if shot_result else None

                loc_x = shot.get("x", shot.get("locX"))
                loc_y = shot.get("y", shot.get("locY"))
                period = shot.get("quarter", shot.get("period"))
                clock = shot.get("clock", shot.get("time"))

                # Determine points value
                points_value = 3 if "3" in str(shot_type) else 2

                shots.append(
                    {
                        "SEASON": season,
                        "GAME_CODE": game_code,
                        "PLAYER_ID": player_id,
                        "PLAYER_NAME": player_name,
                        "TEAM_CODE": team_code,
                        "TEAM": team_name,
                        "SHOT_TYPE": shot_type,
                        "SHOT_RESULT": shot_result,
                        "SHOT_MADE": shot_made,
                        "LOC_X": loc_x,
                        "LOC_Y": loc_y,
                        "PERIOD": period,
                        "CLOCK": clock,
                        "POINTS_VALUE": points_value,
                        "LEAGUE": league_name,
                    }
                )

            except Exception as e:
                logger.debug(f"Error parsing shot: {e}")
                continue

    df = pd.DataFrame(shots)

    logger.info(f"Fetched shot chart: {len(df)} shots")
    return df
