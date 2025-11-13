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
    "api_basketball",  # API-Basketball (api-sports.io)
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
        fetch_player_season: Function to fetch player season stats (if source != "none")
        fetch_team_season: Function to fetch team season stats (if source != "none")
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
    fetch_player_season: Callable[..., pd.DataFrame] | None = None
    fetch_team_season: Callable[..., pd.DataFrame] | None = None
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
    - NBL/ACB/LKL/ABA/BAL/BCL: HTML scaffolds (empty DataFrames)
    - LNB_PROA: team_season works (HTML), player_season scaffold

    **Phase 3 Plan**:
    - NBL/ACB/LKL/BAL/BCL: Migrate to API-Basketball
    - ABA: API-Basketball or RealGM fallback
    - LNB_PROA players: API-Basketball or Statorium
    """
    from ..fetchers import (
        aba,
        acb,
        bal,
        bcl,
        lkl,
        lnb,
        nbl,
        nbl_official,  # NBL Australia via nblR R package
        nz_nbl_fiba,  # NZ NBL via FIBA LiveStats HTML scraping
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
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="Phase 2: ESPN API + cbbpy (fully functional via generic aggregation)",
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
            fetch_player_season=None,  # Uses generic aggregation from player_game
            fetch_team_season=None,  # Uses generic aggregation from team_game
            notes="Phase 2: ESPN API + cbbpy (fully functional via generic aggregation)",
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
            fetch_player_season=None,  # Uses generic aggregation
            fetch_team_season=None,  # Uses generic aggregation
            notes="Phase 2: NBA Stats API (Ignite historical only, program ended 2024, uses generic aggregation)",
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
            fetch_player_season=nbl_official.fetch_nbl_player_season,
            fetch_team_season=nbl_official.fetch_nbl_team_season,
            # Complete dataset loaders available:
            # - nbl_official.fetch_nbl_schedule() - Match results (1979+)
            # - nbl_official.fetch_nbl_player_season() - Player aggregates (2015-16+)
            # - nbl_official.fetch_nbl_team_season() - Team aggregates (2015-16+)
            # - nbl_official.fetch_nbl_player_game() - Player-game box scores (2015-16+)
            # - nbl_official.fetch_nbl_team_game() - Team-game box scores (2015-16+)
            # - nbl_official.fetch_nbl_pbp() - Play-by-play events (2015-16+)
            # - nbl_official.fetch_nbl_shots() - Shot locations with (x,y) coordinates (2015-16+)
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

    # LKL (Lithuania)
    register_league_source(
        LeagueSourceConfig(
            league="LKL",
            player_season_source="html",  # Phase 3: Will change to "api_basketball"
            team_season_source="html",  # Phase 3: Will change to "api_basketball"
            schedule_source="none",
            box_score_source="none",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=lkl.fetch_lkl_player_season,
            fetch_team_season=lkl.fetch_lkl_team_season,
            fallback_source="html_js",
            notes="Phase 2: HTML scaffold (empty). Phase 3: API-Basketball planned.",
        )
    )

    # ABA (Adriatic League)
    register_league_source(
        LeagueSourceConfig(
            league="ABA",
            player_season_source="html",  # Phase 3: API-Basketball or RealGM scraping
            team_season_source="html",
            schedule_source="none",
            box_score_source="none",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=aba.fetch_aba_player_season,
            fetch_team_season=aba.fetch_aba_team_season,
            fallback_source="html_js",
            notes="Phase 2: Roster data only (no stats). Phase 3: API-Basketball or RealGM.",
        )
    )

    # BAL (Basketball Africa League)
    register_league_source(
        LeagueSourceConfig(
            league="BAL",
            player_season_source="html",  # Phase 3: Will change to "api_basketball"
            team_season_source="html",
            schedule_source="none",
            box_score_source="none",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=bal.fetch_bal_player_season,
            fetch_team_season=bal.fetch_bal_team_season,
            fallback_source="html_js",
            notes="Phase 2: HTML scaffold (empty). Phase 3: API-Basketball planned.",
        )
    )

    # BCL (Basketball Champions League)
    register_league_source(
        LeagueSourceConfig(
            league="BCL",
            player_season_source="html",  # Phase 3: Will change to "api_basketball"
            team_season_source="html",
            schedule_source="none",
            box_score_source="none",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=bcl.fetch_bcl_player_season,
            fetch_team_season=bcl.fetch_bcl_team_season,
            fallback_source="html_js",
            notes="Phase 2: HTML scaffold (connection resets). Phase 3: API-Basketball planned.",
        )
    )

    # LNB Pro A (France)
    register_league_source(
        LeagueSourceConfig(
            league="LNB_PROA",
            player_season_source="html",  # Phase 3: Will change to "api_basketball" or "statorium"
            team_season_source="html",  # ✅ WORKS (16 teams via static HTML)
            schedule_source="none",
            box_score_source="none",
            pbp_source="none",
            shots_source="none",
            fetch_player_season=lnb.fetch_lnb_player_season,  # Currently empty scaffold
            fetch_team_season=lnb.fetch_lnb_team_season,  # ✅ Returns 16 teams
            fallback_source="html_js",
            notes="Phase 2: team_season works (16 teams), player_season scaffold. Phase 3: API-Basketball/Statorium for players.",
        )
    )


# ==============================================================================
# Initialization
# ==============================================================================

# Note: _register_league_sources() will be called from api/datasets.py after all imports
# to avoid circular dependency issues. Do not call it here.
