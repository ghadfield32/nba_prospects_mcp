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
    "nbl_official_r",  # NBL Australia via nblR R package (official stats, 1979+)
    "nz_nbl_fiba",  # NZ NBL via FIBA LiveStats HTML scraping
    "statorium",  # Statorium Basketball API
    "espn",  # ESPN API (existing NCAA-MBB/WBB implementation)
    "euroleague_api",  # EuroLeague API package
    "nba_stats",  # NBA Stats API (G-League, WNBA)
    "cbbpy",  # CBBpy package (NCAA box scores)
    "ceblpy",  # CEBLpy package
    "prestosports",  # PrestoSports web scraping (NJCAA, NAIA)
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

    **Phase 2 Status (Current)**:
    - NCAA-MBB/WBB: ESPN API (fully functional)
    - EuroLeague/EuroCup: euroleague-api package (fully functional)
    - G-League: NBA Stats API (fully functional)
    - WNBA: NBA Stats API (fully functional)
    - CEBL: ceblpy + FIBA LiveStats (fully functional)
    - OTE: Web scraping (fully functional)
    - NJCAA/NAIA/U-SPORTS: PrestoSports scraping (fully functional)
    - NBL: nblR R package (fully functional)
    - FIBA Cluster (LKL/BAL/BCL/ABA): FIBA HTML scraping (fully functional)
    - ACB: HTML scaffold (empty DataFrames)
    - LNB_PROA: team_season works (HTML), player_season scaffold

    **Phase 3 Plan**:
    - ACB: Migrate to Statorium or API-Basketball
    - LNB_PROA players: API-Basketball or Statorium
    """
    from ..fetchers import (
        aba,
        acb,
        bal,
        bcl,
        ccaa,  # CCAA (Canada) via PrestoSports
        espn_mbb,  # NCAA Men's Basketball via ESPN API
        espn_wbb,  # NCAA Women's Basketball via ESPN API
        gleague,  # G-League via NBA Stats API
        lkl,
        lnb,
        naia,  # NAIA (USA) via PrestoSports
        nbl_official,  # NBL Australia via nblR R package
        njcaa,  # NJCAA (USA) via PrestoSports
        usports,  # U SPORTS (Canada) via PrestoSports
    )

    # ==========================================================================
    # Fully Functional Leagues (Phase 2 Complete)
    # ==========================================================================

    # NCAA Men's Basketball
    register_league_source(
        LeagueSourceConfig(
            league="NCAA-MBB",
            player_season_source="espn",
            team_season_source="espn",
            schedule_source="espn",
            box_score_source="espn",
            pbp_source="espn",
            shots_source="cbbpy",
            fetch_schedule=espn_mbb.fetch_espn_scoreboard,  # Wired 2025-11-13
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="Phase 2: ESPN API + cbbpy (schedule wired 2025-11-13, season stats via generic aggregation)",
        )
    )

    # NCAA Women's Basketball
    register_league_source(
        LeagueSourceConfig(
            league="NCAA-WBB",
            player_season_source="espn",
            team_season_source="espn",
            schedule_source="espn",
            box_score_source="espn",
            pbp_source="espn",
            shots_source="cbbpy",
            fetch_schedule=espn_wbb.fetch_espn_wbb_scoreboard,  # Wired 2025-11-13
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="Phase 2: ESPN API + cbbpy (schedule wired 2025-11-13, season stats via generic aggregation)",
        )
    )

    # EuroLeague
    register_league_source(
        LeagueSourceConfig(
            league="EuroLeague",
            player_season_source="euroleague_api",
            team_season_source="euroleague_api",
            schedule_source="euroleague_api",
            box_score_source="euroleague_api",
            pbp_source="euroleague_api",
            shots_source="euroleague_api",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: euroleague-api package (fully functional via generic aggregation)",
        )
    )

    # EuroCup
    register_league_source(
        LeagueSourceConfig(
            league="EuroCup",
            player_season_source="euroleague_api",
            team_season_source="euroleague_api",
            schedule_source="euroleague_api",
            box_score_source="euroleague_api",
            pbp_source="euroleague_api",
            shots_source="euroleague_api",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: euroleague-api package (fully functional via generic aggregation)",
        )
    )

    # G-League
    register_league_source(
        LeagueSourceConfig(
            league="G-League",
            player_season_source="nba_stats",
            team_season_source="nba_stats",
            schedule_source="nba_stats",
            box_score_source="nba_stats",
            pbp_source="nba_stats",
            shots_source="nba_stats",
            fetch_schedule=gleague.fetch_gleague_schedule,  # Wired 2025-11-13
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: NBA Stats API (schedule wired 2025-11-13, Ignite historical only, season stats via generic aggregation)",
        )
    )

    # WNBA
    register_league_source(
        LeagueSourceConfig(
            league="WNBA",
            player_season_source="nba_stats",
            team_season_source="nba_stats",
            schedule_source="nba_stats",
            box_score_source="nba_stats",
            pbp_source="nba_stats",
            shots_source="nba_stats",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: NBA Stats API (fully functional via generic aggregation)",
        )
    )

    # CEBL
    register_league_source(
        LeagueSourceConfig(
            league="CEBL",
            player_season_source="ceblpy",
            team_season_source="ceblpy",
            schedule_source="ceblpy",
            box_score_source="ceblpy",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: ceblpy + FIBA LiveStats JSON (fully functional via generic aggregation)",
        )
    )

    # OTE (Overtime Elite)
    register_league_source(
        LeagueSourceConfig(
            league="OTE",
            player_season_source="html",
            team_season_source="html",
            schedule_source="html",
            box_score_source="html",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: Web scraping (fully functional via generic aggregation)",
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
            player_season_source="nz_nbl_fiba",  # FIBA LiveStats HTML scraping
            team_season_source="nz_nbl_fiba",
            schedule_source="nz_nbl_fiba",  # Via pre-built game index
            box_score_source="nz_nbl_fiba",  # HTML scraping
            pbp_source="nz_nbl_fiba",  # HTML scraping
            shots_source="none",  # FIBA HTML doesn't provide x,y coordinates
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            # Complete dataset loaders available:
            # - nz_nbl_fiba.fetch_nz_nbl_schedule() - Via game index
            # - nz_nbl_fiba.fetch_nz_nbl_player_game() - HTML scraping
            # - nz_nbl_fiba.fetch_nz_nbl_team_game() - Aggregated from player stats
            # - nz_nbl_fiba.fetch_nz_nbl_pbp() - HTML scraping
            notes="FIBA LiveStats HTML scraping (NZN code). Requires pre-built game index (data/nz_nbl_game_index.csv). HTML parsing scaffold in place.",
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
            schedule_source="none",
            box_score_source="none",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=acb.fetch_acb_player_season,
            fetch_team_season=acb.fetch_acb_team_season,
            fallback_source="html_js",
            notes="Phase 2: HTML scaffold (404 errors). Phase 3: Statorium or API-Basketball planned.",
        )
    )

    # LNB Pro A (France) - API Integration Complete
    register_league_source(
        LeagueSourceConfig(
            league="LNB_PROA",
            player_season_source="lnb_api",  # LNB Official API (via lnb_api.py client)
            team_season_source="lnb_api",  # LNB Official API
            schedule_source="lnb_api",  # LNB Official API
            box_score_source="html",  # Boxscore endpoint not yet discovered
            pbp_source="none",
            shots_source="none",
            fetch_schedule=lnb.fetch_lnb_schedule_v2,  # ✅ API-based schedule
            fetch_player_season=lnb.fetch_lnb_player_season_v2,  # ✅ API-based player stats
            fetch_team_season=lnb.fetch_lnb_team_season_v2,  # ✅ API-based team standings
            fetch_player_game=lnb.fetch_lnb_player_game,  # Placeholder (boxscore endpoint TODO)
            fallback_source="html",  # Old HTML scrapers as backup
            notes="Phase 4-5 COMPLETE: LNB Official API integration. Schedule, player_season, team_season functional. Boxscore endpoint discovery pending.",
        )
    )


# ==============================================================================
# Initialization
# ==============================================================================

# Note: _register_league_sources() will be called from api/datasets.py after all imports
# to avoid circular dependency issues. Do not call it here.
