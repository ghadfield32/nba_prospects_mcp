"""League Data Source Configuration

Central registry of data sources for each league. This config-driven approach eliminates
scattered if/else logic and makes adding new leagues or swapping data sources trivial.

Usage:
    # Get config for a league
    cfg = get_league_source_config("NBL")

    # Fetch player season stats using configured source
    if cfg and cfg.fetch_player_season:
        df = cfg.fetch_player_season(season="2024", per_mode="Totals")

Design Principles:
- **Config over code**: Changing data sources is a config edit, not code refactor
- **Graceful fallback**: Each league can specify primary + fallback sources
- **Source attribution**: Track which source provided data (for monitoring/debugging)
- **Easy testing**: Mock configs for testing without hitting external APIs
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import pandas as pd

# Type alias for source identifiers
SourceType = Literal[
    "html",  # Static HTML scraping (pandas.read_html)
    "html_js",  # JavaScript-rendered HTML (requires Selenium/Playwright)
    "fiba_html",  # FIBA LiveStats HTML scraping (LKL, BAL, BCL, ABA)
    "api_basketball",  # API-Basketball (api-sports.io)
    "lnb_api",  # LNB Official API (France - Betclic ÉLITE)
    "lnb_normalized",  # LNB normalized parquet files (Elite 2, Espoirs leagues)
    "lnb_aggregated",  # LNB aggregated statistics from normalized player_game/team_game data
    "nbl_official_r",  # NBL Australia via nblR R package (official stats, 1979+)
    "nz_nbl_fiba",  # NZ NBL via FIBA LiveStats HTML scraping
    "statorium",  # Statorium Basketball API
    "espn",  # ESPN API (existing NCAA-MBB/WBB implementation)
    "euroleague_api",  # EuroLeague API package
    "nba_stats",  # NBA Stats API (G-League, WNBA)
    "cbbpy",  # CBBpy package (NCAA box scores)
    "ceblpy",  # CEBLpy package
    "prestosports",  # PrestoSports web scraping (NJCAA, NAIA)
    "bawir",  # BAwiR R package for ACB (Spain) PBP/shots
    "none",  # No source available (returns empty DataFrame)
]


@dataclass(frozen=True)
class LeagueSourceConfig:
    """Configuration for data sources per league

    Attributes:
        league: League identifier (matches LEAGUE_LEVELS keys)
        player_season_source: Primary source for player season aggregates
        team_season_source: Primary source for team season aggregates
        schedule_source: Source for game schedules
        box_score_source: Source for per-game box scores
        pbp_source: Source for play-by-play data
        shots_source: Source for shot chart data
        fetch_schedule: Function to fetch schedule/game results
        fetch_player_season: Function to fetch player season stats
        fetch_team_season: Function to fetch team season stats
        fetch_player_game: Function to fetch player per-game box scores
        fetch_team_game: Function to fetch team per-game box scores
        fetch_pbp: Function to fetch play-by-play events
        fetch_shots: Function to fetch shot chart data
        fallback_source: Alternative source if primary fails
        notes: Implementation notes, caveats, or status
    """

    league: str
    player_season_source: SourceType
    team_season_source: SourceType
    schedule_source: SourceType = "none"
    box_score_source: SourceType = "none"
    pbp_source: SourceType = "none"
    shots_source: SourceType = "none"
    fetch_schedule: Callable[..., pd.DataFrame] | None = None
    fetch_player_season: Callable[..., pd.DataFrame] | None = None
    fetch_team_season: Callable[..., pd.DataFrame] | None = None
    fetch_player_game: Callable[..., pd.DataFrame] | None = None
    fetch_team_game: Callable[..., pd.DataFrame] | None = None
    fetch_pbp: Callable[..., pd.DataFrame] | None = None
    fetch_shots: Callable[..., pd.DataFrame] | None = None
    fallback_source: SourceType | None = None
    notes: str = ""


# ==============================================================================
# League Source Registry
# ==============================================================================
# This will be populated after all fetchers are imported to avoid circular imports
# See _register_league_sources() below
LEAGUE_SOURCES: dict[str, LeagueSourceConfig] = {}


def get_league_source_config(league: str) -> LeagueSourceConfig | None:
    """Get data source configuration for a league

    Args:
        league: League identifier (e.g., "NBL", "ACB", "NCAA-MBB")

    Returns:
        LeagueSourceConfig if league is registered, None otherwise

    Example:
        >>> cfg = get_league_source_config("NBL")
        >>> if cfg and cfg.fetch_player_season:
        ...     df = cfg.fetch_player_season(season="2024")
    """
    return LEAGUE_SOURCES.get(league)


def list_leagues_by_source(source: SourceType) -> list[str]:
    """Get all leagues using a specific data source

    Args:
        source: Source type to filter by

    Returns:
        List of league identifiers using this source

    Example:
        >>> api_leagues = list_leagues_by_source("api_basketball")
        >>> print(api_leagues)  # ["NBL", "ACB", "BAL", ...]
    """
    return [
        league
        for league, cfg in LEAGUE_SOURCES.items()
        if cfg.player_season_source == source or cfg.team_season_source == source
    ]


def register_league_source(config: LeagueSourceConfig) -> None:
    """Register or update a league source configuration

    Args:
        config: LeagueSourceConfig to register

    Example:
        >>> from cbb_data.fetchers.nbl import fetch_nbl_player_season_via_api
        >>> register_league_source(LeagueSourceConfig(
        ...     league="NBL",
        ...     player_season_source="api_basketball",
        ...     team_season_source="api_basketball",
        ...     fetch_player_season=fetch_nbl_player_season_via_api,
        ...     notes="Phase 3: API-Basketball integration",
        ... ))
    """
    LEAGUE_SOURCES[config.league] = config


# ==============================================================================
# Default League Source Configurations
# ==============================================================================


def _register_league_sources() -> None:
    """Register all league source configurations

    Called after all fetcher modules are imported to avoid circular dependencies.
    This function should be called from api/datasets.py after imports.

    **Phase 2 Status (Current)** - Updated 2025-11-19:
    - NCAA-MBB/WBB: ESPN API (fully functional)
    - EuroLeague/EuroCup: euroleague-api package (✅ FULLY WIRED - schedule, box, pbp, shots)
    - G-League: NBA Stats API (✅ FULLY WIRED - schedule, box, pbp, shots)
    - WNBA: NBA Stats API (✅ FULLY WIRED - schedule, box, pbp, shots)
    - CEBL: ceblpy + FIBA LiveStats (fully functional)
    - OTE: Web scraping (✅ FULLY WIRED - schedule, box, pbp)
    - NJCAA/NAIA/U-SPORTS: PrestoSports scraping (fully functional)
    - NBL: nblR R package (fully functional)
    - FIBA Cluster (LKL/BAL/BCL/ABA): FIBA HTML scraping (fully functional)
    - ACB: BAwiR R package (✅ FULLY WIRED - schedule, box, pbp, shots)
    - LNB_PROA: LNB API (✅ FULLY WIRED - schedule, box, pbp, shots)

    **Data Availability Matrix Status**:
    - Tier 0 (Core Feeders): NCAA, EuroLeague, EuroCup, G-League, OTE, WNBA - COMPLETE
    - Tier 1 (Secondary): CEBL, NZ-NBL, LNB_PROA, ACB, NBL - COMPLETE
    - Tier 2 (Development): NJCAA, NAIA, USPORTS, CCAA, ABA/BAL/BCL - COMPLETE
    """
    from ..fetchers import (
        aba,
        acb,
        bal,
        bcl,
        cbbpy_mbb,  # NCAA MBB box scores, PBP via cbbpy
        cbbpy_wbb,  # NCAA WBB box scores, PBP via cbbpy
        ccaa,  # CCAA (Canada) via PrestoSports
        cebl,  # CEBL via ceblpy + FIBA LiveStats
        espn_mbb,  # NCAA Men's Basketball via ESPN API
        espn_wbb,  # NCAA Women's Basketball via ESPN API
        euroleague,  # EuroLeague/EuroCup via euroleague-api package
        gleague,  # G-League via NBA Stats API
        lkl,
        lnb,
        naia,  # NAIA (USA) via PrestoSports
        nbl_official,  # NBL Australia via nblR R package
        njcaa,  # NJCAA (USA) via PrestoSports
        nz_nbl_fiba,  # NZ NBL via FIBA LiveStats HTML scraping
        ote,  # Overtime Elite via web scraping
        usports,  # U SPORTS (Canada) via PrestoSports
        wnba,  # WNBA via NBA Stats API
    )

    # ==========================================================================
    # Fully Functional Leagues (Phase 2 Complete)
    # ==========================================================================

    # NCAA Men's Basketball - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="NCAA-MBB",
            player_season_source="espn",
            team_season_source="espn",
            schedule_source="espn",
            box_score_source="cbbpy",
            pbp_source="cbbpy",
            shots_source="none",  # Shot locations embedded in PBP data
            fetch_schedule=espn_mbb.fetch_espn_scoreboard,
            fetch_player_game=cbbpy_mbb.fetch_cbbpy_box_score,
            fetch_pbp=cbbpy_mbb.fetch_cbbpy_pbp,
            fetch_shots=None,  # Extract shots from PBP with shot_type filter
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            fetch_team_game=None,  # Team box scores via aggregation from player_game
            notes="✅ WIRED (2025-11-19): ESPN schedule + cbbpy box/PBP. Shots embedded in PBP (x,y coords). Season/team stats via aggregation.",
        )
    )

    # NCAA Women's Basketball - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="NCAA-WBB",
            player_season_source="espn",
            team_season_source="espn",
            schedule_source="espn",
            box_score_source="cbbpy",
            pbp_source="cbbpy",
            shots_source="none",  # Shot locations embedded in PBP data
            fetch_schedule=espn_wbb.fetch_espn_wbb_scoreboard,
            fetch_player_game=cbbpy_wbb.fetch_cbbpy_wbb_box_score,
            fetch_pbp=cbbpy_wbb.fetch_cbbpy_wbb_pbp,
            fetch_shots=None,  # Extract shots from PBP with shot_type filter
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            fetch_team_game=None,  # Team box scores via aggregation from player_game
            notes="✅ WIRED (2025-11-19): ESPN schedule + cbbpy box/PBP. Shots embedded in PBP (x,y coords). Season/team stats via aggregation.",
        )
    )

    # EuroLeague - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="EuroLeague",
            player_season_source="euroleague_api",
            team_season_source="euroleague_api",
            schedule_source="euroleague_api",
            box_score_source="euroleague_api",
            pbp_source="euroleague_api",
            shots_source="euroleague_api",
            fetch_schedule=lambda season, **kw: euroleague.fetch_euroleague_games(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                competition="E",
                **kw,
            ),
            fetch_player_game=lambda game_id,
            season="2024",
            **kw: euroleague.fetch_euroleague_box_score(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                int(game_id),
                competition="E",
            ),
            fetch_pbp=lambda game_id, season="2024", **kw: euroleague.fetch_euroleague_play_by_play(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                int(game_id),
                competition="E",
            ),
            fetch_shots=lambda game_id, season="2024", **kw: euroleague.fetch_euroleague_shot_data(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                int(game_id),
                competition="E",
            ),
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="✅ FULLY WIRED (2025-11-19): 6/6 datasets. euroleague-api package. Historical data 2000+. Rate limit 2 req/sec.",
        )
    )

    # EuroCup - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="EuroCup",
            player_season_source="euroleague_api",
            team_season_source="euroleague_api",
            schedule_source="euroleague_api",
            box_score_source="euroleague_api",
            pbp_source="euroleague_api",
            shots_source="euroleague_api",
            fetch_schedule=lambda season, **kw: euroleague.fetch_euroleague_games(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                competition="U",
                **kw,
            ),
            fetch_player_game=lambda game_id,
            season="2024",
            **kw: euroleague.fetch_euroleague_box_score(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                int(game_id),
                competition="U",
            ),
            fetch_pbp=lambda game_id, season="2024", **kw: euroleague.fetch_euroleague_play_by_play(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                int(game_id),
                competition="U",
            ),
            fetch_shots=lambda game_id, season="2024", **kw: euroleague.fetch_euroleague_shot_data(
                int(season.split("-")[0]) if "-" in str(season) else int(season),
                int(game_id),
                competition="U",
            ),
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="✅ FULLY WIRED (2025-11-19): 6/6 datasets. euroleague-api package. Historical data 2000+. Rate limit 2 req/sec.",
        )
    )

    # G-League - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="G-League",
            player_season_source="nba_stats",
            team_season_source="nba_stats",
            schedule_source="nba_stats",
            box_score_source="nba_stats",
            pbp_source="nba_stats",
            shots_source="nba_stats",
            fetch_schedule=gleague.fetch_gleague_schedule,
            fetch_player_game=gleague.fetch_gleague_box_score,
            fetch_pbp=gleague.fetch_gleague_play_by_play,
            fetch_shots=gleague.fetch_gleague_shot_chart,
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="✅ FULLY WIRED (2025-11-19): 6/6 datasets. NBA Stats API (stats.gleague.nba.com). Historical data 2001+. Rate limit 5 req/sec.",
        )
    )

    # WNBA - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="WNBA",
            player_season_source="nba_stats",
            team_season_source="nba_stats",
            schedule_source="nba_stats",
            box_score_source="nba_stats",
            pbp_source="nba_stats",
            shots_source="nba_stats",
            fetch_schedule=wnba.fetch_wnba_schedule,
            fetch_player_game=wnba.fetch_wnba_box_score,
            fetch_pbp=wnba.fetch_wnba_play_by_play,
            fetch_shots=wnba.fetch_wnba_shot_chart,
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="✅ FULLY WIRED (2025-11-19): 6/6 datasets. NBA Stats API (stats.wnba.com). Historical data 1997+. Rate limit 5 req/sec.",
        )
    )

    # CEBL - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="CEBL",
            player_season_source="ceblpy",
            team_season_source="ceblpy",
            schedule_source="ceblpy",
            box_score_source="ceblpy",
            pbp_source="ceblpy",
            shots_source="ceblpy",
            fetch_schedule=cebl.fetch_cebl_schedule,
            fetch_player_game=cebl.fetch_cebl_box_score,
            fetch_pbp=cebl.fetch_cebl_play_by_play,
            fetch_shots=cebl.fetch_cebl_shot_chart,
            fetch_player_season=cebl.fetch_cebl_season_stats,
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="✅ WIRED (2025-11-19): 6/6 datasets. ceblpy + FIBA LiveStats. 2019+ data.",
        )
    )

    # OTE (Overtime Elite) - ✅ FULLY WIRED 2025-11-19
    register_league_source(
        LeagueSourceConfig(
            league="OTE",
            player_season_source="html",
            team_season_source="html",
            schedule_source="html",
            box_score_source="html",
            pbp_source="html",  # ✅ OTE publishes FULL PBP (rare for non-NBA leagues!)
            shots_source="none",  # Shot coordinates not available
            fetch_schedule=ote.fetch_ote_schedule,
            fetch_player_game=ote.fetch_ote_box_score,
            fetch_pbp=ote.fetch_ote_play_by_play,  # ✅ Full PBP available!
            fetch_shots=ote.fetch_ote_shot_chart,  # Returns empty (no coordinates)
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="✅ FULLY WIRED (2025-11-19): 5/6 datasets. Web scraping (overtimeelite.com). UNIQUE: Full PBP published! Key NBA prospect pipeline (ages 16-20). Shots unavailable (no x,y coords).",
        )
    )

    # NJCAA
    register_league_source(
        LeagueSourceConfig(
            league="NJCAA",
            player_season_source="prestosports",
            team_season_source="prestosports",
            schedule_source="prestosports",
            box_score_source="prestosports",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: PrestoSports scraping (fully functional via generic aggregation)",
        )
    )

    # NAIA
    register_league_source(
        LeagueSourceConfig(
            league="NAIA",
            player_season_source="prestosports",
            team_season_source="prestosports",
            schedule_source="prestosports",
            box_score_source="prestosports",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: PrestoSports scraping (fully functional via generic aggregation)",
        )
    )

    # ==========================================================================
    # PrestoSports Cluster - US & Canadian Leagues (Phase 2 COMPLETE)
    # ==========================================================================

    # USPORTS (U SPORTS - Canadian University Basketball)
    register_league_source(
        LeagueSourceConfig(
            league="USPORTS",
            player_season_source="prestosports",
            team_season_source="prestosports",
            schedule_source="prestosports",
            box_score_source="prestosports",
            pbp_source="none",
            shots_source="none",
            fetch_schedule=usports.fetch_schedule,
            fetch_player_game=usports.fetch_player_game,
            fetch_team_game=usports.fetch_team_game,
            fetch_pbp=usports.fetch_pbp,
            fetch_player_season=usports.fetch_player_season,
            fetch_team_season=usports.fetch_team_season,
            notes="Phase 2: PrestoSports scraping COMPLETE. Season leaders functional, schedule/box scores scaffold.",
        )
    )

    # CCAA (Canadian Collegiate Athletic Association)
    register_league_source(
        LeagueSourceConfig(
            league="CCAA",
            player_season_source="prestosports",
            team_season_source="prestosports",
            schedule_source="prestosports",
            box_score_source="prestosports",
            pbp_source="none",
            shots_source="none",
            fetch_schedule=ccaa.fetch_schedule,
            fetch_player_game=ccaa.fetch_player_game,
            fetch_team_game=ccaa.fetch_team_game,
            fetch_pbp=ccaa.fetch_pbp,
            fetch_player_season=ccaa.fetch_player_season,
            fetch_team_season=ccaa.fetch_team_season,
            notes="Phase 2: PrestoSports scraping COMPLETE. Season leaders functional, schedule/box scores scaffold.",
        )
    )

    # NAIA (National Association of Intercollegiate Athletics - USA Small College)
    register_league_source(
        LeagueSourceConfig(
            league="NAIA",
            player_season_source="prestosports",
            team_season_source="prestosports",
            schedule_source="prestosports",
            box_score_source="prestosports",
            pbp_source="none",
            shots_source="none",
            fetch_schedule=naia.fetch_schedule,
            fetch_player_game=naia.fetch_player_game,
            fetch_team_game=naia.fetch_team_game,
            fetch_pbp=naia.fetch_pbp,
            fetch_player_season=naia.fetch_player_season,
            fetch_team_season=naia.fetch_team_season,
            notes="Phase 2: PrestoSports scraping COMPLETE. Season leaders functional, schedule/box scores scaffold. Pre-NBA prospect pipeline.",
        )
    )

    # NJCAA (National Junior College Athletic Association - USA Junior College)
    register_league_source(
        LeagueSourceConfig(
            league="NJCAA",
            player_season_source="prestosports",
            team_season_source="prestosports",
            schedule_source="prestosports",
            box_score_source="prestosports",
            pbp_source="none",
            shots_source="none",
            fetch_schedule=njcaa.fetch_schedule,
            fetch_player_game=njcaa.fetch_player_game,
            fetch_team_game=njcaa.fetch_team_game,
            fetch_pbp=njcaa.fetch_pbp,
            fetch_player_season=njcaa.fetch_player_season,
            fetch_team_season=njcaa.fetch_team_season,
            notes="Phase 2: PrestoSports scraping COMPLETE. Season leaders functional, schedule/box scores scaffold. Pre-NBA prospect pipeline.",
        )
    )

    # NZ NBL (New Zealand National Basketball League)
    register_league_source(
        LeagueSourceConfig(
            league="NZ-NBL",
            player_season_source="nz_nbl_fiba",  # FIBA LiveStats HTML scraping (aggregated)
            team_season_source="nz_nbl_fiba",  # FIBA LiveStats HTML scraping (aggregated)
            schedule_source="html_js",  # Via Playwright JS rendering (Genius widget)
            box_score_source="nz_nbl_fiba",  # HTML scraping
            pbp_source="nz_nbl_fiba",  # HTML scraping
            shots_source="nz_nbl_fiba",  # ✅ ADDED 2025-11-18: FIBA HTML/JS extraction
            fetch_schedule=nz_nbl_fiba.fetch_nz_nbl_schedule_full,  # ✅ UPDATED: Playwright-based (with fallback)
            fetch_player_game=nz_nbl_fiba.fetch_nz_nbl_player_game,  # ✅ WIRED 2025-11-18
            fetch_team_game=nz_nbl_fiba.fetch_nz_nbl_team_game,  # ✅ WIRED 2025-11-18
            fetch_pbp=nz_nbl_fiba.fetch_nz_nbl_pbp,  # ✅ WIRED 2025-11-18
            fetch_shots=nz_nbl_fiba.fetch_nz_nbl_shot_chart,  # ✅ ADDED 2025-11-18
            fetch_player_season=nz_nbl_fiba.fetch_nz_nbl_player_season,  # ✅ ADDED 2025-11-18 (aggregated from player_game)
            fetch_team_season=nz_nbl_fiba.fetch_nz_nbl_team_season,  # ✅ ADDED 2025-11-18 (aggregated from team_game)
            notes="✅ EXPANDED (2025-11-18): 7/7 datasets. Playwright JS rendering for schedule (Genius widget). FIBA LiveStats HTML for box/PBP/shots. Install: uv pip install 'cbb-data[nz_nbl]' && playwright install chromium",
        )
    )

    # ==========================================================================
    # FIBA HTML Cluster (Phase 2 COMPLETE)
    # ==========================================================================

    # LKL (Lithuania Basketball League) - FIBA HTML Scraping
    register_league_source(
        LeagueSourceConfig(
            league="LKL",
            player_season_source="fiba_html",
            team_season_source="fiba_html",
            schedule_source="fiba_html",
            box_score_source="fiba_html",
            pbp_source="fiba_html",
            shots_source="none",
            fetch_schedule=lkl.fetch_schedule,
            fetch_player_game=lkl.fetch_player_game,
            fetch_team_game=lkl.fetch_team_game,
            fetch_pbp=lkl.fetch_pbp,
            fetch_player_season=lkl.fetch_player_season,
            fetch_team_season=lkl.fetch_team_season,
            notes="Phase 2: FIBA HTML scraping COMPLETE. Schedule via game index, box scores + PBP via HTML parsing. Season aggregates via generic aggregation.",
        )
    )

    # BAL (Basketball Africa League) - FIBA HTML Scraping
    register_league_source(
        LeagueSourceConfig(
            league="BAL",
            player_season_source="fiba_html",
            team_season_source="fiba_html",
            schedule_source="fiba_html",
            box_score_source="fiba_html",
            pbp_source="fiba_html",
            shots_source="none",
            fetch_schedule=bal.fetch_schedule,
            fetch_player_game=bal.fetch_player_game,
            fetch_team_game=bal.fetch_team_game,
            fetch_pbp=bal.fetch_pbp,
            fetch_player_season=bal.fetch_player_season,
            fetch_team_season=bal.fetch_team_season,
            notes="Phase 2: FIBA HTML scraping COMPLETE. Schedule via game index, box scores + PBP via HTML parsing. Season aggregates via generic aggregation.",
        )
    )

    # BCL (Basketball Champions League) - FIBA HTML Scraping
    register_league_source(
        LeagueSourceConfig(
            league="BCL",
            player_season_source="fiba_html",
            team_season_source="fiba_html",
            schedule_source="fiba_html",
            box_score_source="fiba_html",
            pbp_source="fiba_html",
            shots_source="none",
            fetch_schedule=bcl.fetch_schedule,
            fetch_player_game=bcl.fetch_player_game,
            fetch_team_game=bcl.fetch_team_game,
            fetch_pbp=bcl.fetch_pbp,
            fetch_player_season=bcl.fetch_player_season,
            fetch_team_season=bcl.fetch_team_season,
            notes="Phase 2: FIBA HTML scraping COMPLETE. Schedule via game index, box scores + PBP via HTML parsing. Season aggregates via generic aggregation.",
        )
    )

    # ABA (Adriatic League) - FIBA HTML Scraping
    register_league_source(
        LeagueSourceConfig(
            league="ABA",
            player_season_source="fiba_html",
            team_season_source="fiba_html",
            schedule_source="fiba_html",
            box_score_source="fiba_html",
            pbp_source="fiba_html",
            shots_source="none",
            fetch_schedule=aba.fetch_schedule,
            fetch_player_game=aba.fetch_player_game,
            fetch_team_game=aba.fetch_team_game,
            fetch_pbp=aba.fetch_pbp,
            fetch_player_season=aba.fetch_player_season,
            fetch_team_season=aba.fetch_team_season,
            notes="Phase 2: FIBA HTML scraping COMPLETE. Schedule via game index, box scores + PBP via HTML parsing. Season aggregates via generic aggregation.",
        )
    )

    # ==========================================================================
    # Phase 2 Scaffolds (Empty DataFrames) - Phase 3 Will Add Real Data
    # ==========================================================================

    # NBL (Australia) - Official Stats via nblR R Package
    register_league_source(
        LeagueSourceConfig(
            league="NBL",
            player_season_source="nbl_official_r",  # nblR R package (CRAN, GPL-3)
            team_season_source="nbl_official_r",
            schedule_source="nbl_official_r",  # Match results back to 1979!
            box_score_source="nbl_official_r",  # Since 2015-16
            pbp_source="nbl_official_r",  # Since 2015-16
            shots_source="nbl_official_r",  # Shot locations (x,y) since 2015-16!
            fetch_schedule=nbl_official.fetch_nbl_schedule,
            fetch_player_season=nbl_official.fetch_nbl_player_season,
            fetch_team_season=nbl_official.fetch_nbl_team_season,
            fetch_player_game=nbl_official.fetch_nbl_player_game,
            fetch_team_game=nbl_official.fetch_nbl_team_game,
            fetch_pbp=nbl_official.fetch_nbl_pbp,
            fetch_shots=nbl_official.fetch_nbl_shots,
            fallback_source="api_basketball",  # API-Basketball as backup
            notes="nblR R package integration COMPLETE. All datasets: schedule (1979+), player/team season+game, pbp, shots (x,y coordinates 2015-16+). Requires: R + nblR/arrow packages.",
        )
    )

    # ACB (Spain)
    register_league_source(
        LeagueSourceConfig(
            league="ACB",
            player_season_source="html",  # Phase 3: Will change to "api_basketball" or "statorium"
            team_season_source="html",  # Phase 3: Will change to "api_basketball" or "statorium"
            schedule_source="html",  # ✅ WIRED 2025-11-18: HTML scraping from /calendario page
            box_score_source="html",  # ✅ WIRED 2025-11-18: HTML table parsing from game pages
            pbp_source="bawir",  # ✅ WIRED 2025-11-18: BAwiR R package via rpy2
            shots_source="bawir",  # ✅ WIRED 2025-11-18: BAwiR R package via rpy2
            fetch_schedule=acb.fetch_acb_schedule,  # ✅ WIRED 2025-11-18
            fetch_player_game=acb.fetch_acb_box_score,  # ✅ WIRED 2025-11-18
            fetch_pbp=acb.fetch_acb_pbp_bawir,  # ✅ WIRED 2025-11-18: BAwiR via rpy2
            fetch_shots=acb.fetch_acb_shot_chart_bawir,  # ✅ WIRED 2025-11-18: BAwiR via rpy2
            fetch_player_season=acb.fetch_acb_player_season,
            fetch_team_season=acb.fetch_acb_team_season,
            fallback_source="html_js",
            notes="✅ FULLY IMPLEMENTED (2025-11-18): 6/7 datasets. Schedule/box via HTML. PBP/shots via BAwiR R package. Install: uv pip install 'cbb-data[acb]' && R -e \"install.packages('BAwiR')\"",
        )
    )

    # LNB Betclic ELITE (France) - formerly Pro A - Top-tier professional (16 teams)
    register_league_source(
        LeagueSourceConfig(
            league="LNB_PROA",
            player_season_source="lnb_api",  # LNB Official API (via lnb_api.py client)
            team_season_source="lnb_api",  # LNB Official API
            schedule_source="lnb_api",  # LNB Official API
            box_score_source="lnb_api",  # Normalized parquet files (via lnb_historical.py)
            pbp_source="lnb_api",  # Historical parquet files (via lnb_historical.py)
            shots_source="lnb_api",  # Historical parquet files (via lnb_historical.py)
            fetch_schedule=lnb.fetch_lnb_schedule_v2,  # ✅ API-based schedule
            fetch_player_season=lnb.fetch_lnb_player_season,  # ✅ Playwright-based stats (matches API signature)
            fetch_team_season=lnb.fetch_lnb_team_season_v2,  # ✅ API-based team standings
            fetch_player_game=lnb.fetch_lnb_player_game_normalized,  # ✅ Normalized parquet (27 cols, 4 seasons)
            fetch_team_game=lnb.fetch_lnb_team_game_normalized,  # ✅ Normalized parquet (26 cols, 4 seasons)
            fetch_pbp=lnb.fetch_proa_pbp,  # ✅ Historical PBP data (league-filtered)
            fetch_shots=lnb.fetch_proa_shots,  # ✅ Historical shots data (league-filtered)
            fallback_source="html",  # Old HTML scrapers as backup
            notes="✅ COMPLETE (2025-11-18): Betclic ELITE (formerly Pro A) - 7/7 datasets functional. API-based schedule/season stats + normalized parquet box scores (2021-2025) + historical PBP/shots (2025-2026). Part of LNB multi-league expansion (4 leagues total).",
        )
    )

    # LNB ELITE 2 (France) - formerly Pro B - Second-tier professional (20 teams)
    register_league_source(
        LeagueSourceConfig(
            league="LNB_ELITE2",
            player_season_source="lnb_aggregated",  # Aggregated from player_game
            team_season_source="lnb_aggregated",  # Aggregated from team_game
            schedule_source="lnb_aggregated",  # Extracted from team_game
            box_score_source="lnb_normalized",
            pbp_source="lnb_normalized",
            shots_source="lnb_normalized",
            fetch_schedule=lnb.fetch_elite2_schedule,  # ✅ From team_game data
            fetch_player_season=lnb.fetch_elite2_player_season,  # ✅ Aggregated
            fetch_team_season=lnb.fetch_elite2_team_season,  # ✅ Aggregated
            fetch_player_game=lnb.fetch_elite2_player_game,
            fetch_team_game=lnb.fetch_elite2_team_game,
            fetch_pbp=lnb.fetch_elite2_pbp,  # ✅ League-specific PBP
            fetch_shots=lnb.fetch_elite2_shots,  # ✅ League-specific shots
            notes="✅ COMPLETE (2025-11-19): Elite 2 - 7/7 datasets. Box + PBP + shots via league wrappers, schedule/season via aggregation.",
        )
    )

    # LNB Espoirs ELITE (France) - U21 top-tier youth league
    register_league_source(
        LeagueSourceConfig(
            league="LNB_ESPOIRS_ELITE",
            player_season_source="lnb_aggregated",  # Aggregated from player_game
            team_season_source="lnb_aggregated",  # Aggregated from team_game
            schedule_source="lnb_aggregated",  # Extracted from team_game
            box_score_source="lnb_normalized",  # Normalized parquet files
            pbp_source="lnb_normalized",  # Historical parquet files
            shots_source="lnb_normalized",  # Historical parquet files
            fetch_schedule=lnb.fetch_espoirs_elite_schedule,  # ✅ From team_game data
            fetch_player_season=lnb.fetch_espoirs_elite_player_season,  # ✅ Aggregated
            fetch_team_season=lnb.fetch_espoirs_elite_team_season,  # ✅ Aggregated
            fetch_player_game=lnb.fetch_espoirs_elite_player_game,  # ✅ League-specific wrapper
            fetch_team_game=lnb.fetch_espoirs_elite_team_game,  # ✅ League-specific wrapper
            fetch_pbp=lnb.fetch_espoirs_elite_pbp,  # ✅ League-specific PBP
            fetch_shots=lnb.fetch_espoirs_elite_shots,  # ✅ League-specific shots
            notes="✅ COMPLETE (2025-11-19): Espoirs ELITE - 7/7 datasets. Box + PBP + shots via league wrappers, schedule/season via aggregation.",
        )
    )

    # LNB Espoirs PROB (France) - U21 second-tier youth league
    register_league_source(
        LeagueSourceConfig(
            league="LNB_ESPOIRS_PROB",
            player_season_source="lnb_aggregated",  # Aggregated from player_game
            team_season_source="lnb_aggregated",  # Aggregated from team_game
            schedule_source="lnb_aggregated",  # Extracted from team_game
            box_score_source="lnb_normalized",  # Normalized parquet files
            pbp_source="lnb_normalized",  # Historical parquet files
            shots_source="lnb_normalized",  # Historical parquet files
            fetch_schedule=lnb.fetch_espoirs_prob_schedule,  # ✅ From team_game data
            fetch_player_season=lnb.fetch_espoirs_prob_player_season,  # ✅ Aggregated
            fetch_team_season=lnb.fetch_espoirs_prob_team_season,  # ✅ Aggregated
            fetch_player_game=lnb.fetch_espoirs_prob_player_game,  # ✅ League-specific wrapper
            fetch_team_game=lnb.fetch_espoirs_prob_team_game,  # ✅ League-specific wrapper
            fetch_pbp=lnb.fetch_espoirs_prob_pbp,  # ✅ League-specific PBP
            fetch_shots=lnb.fetch_espoirs_prob_shots,  # ✅ League-specific shots
            notes="✅ COMPLETE (2025-11-19): Espoirs PROB - 7/7 datasets. Box + PBP + shots via league wrappers, schedule/season via aggregation.",
        )
    )


# ==============================================================================
# Initialization
# ==============================================================================

# Note: _register_league_sources() will be called from api/datasets.py after all imports
# to avoid circular dependency issues. Do not call it here.
