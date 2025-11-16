"""Generate comprehensive league coverage matrix for README

This script analyzes all registered leagues and their dataset capabilities
to generate accurate documentation for the README.

Usage:
    python tools/generate_league_coverage_matrix.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cbb_data.catalog.levels import LEAGUE_LEVELS
from cbb_data.catalog.sources import LEAGUE_SOURCES, _register_league_sources


def get_dataset_status(config, dataset_type: str) -> str:
    """Determine status of a dataset for a league

    Args:
        config: LeagueSourceConfig
        dataset_type: One of: schedule, player_game, team_game, player_season, team_season, pbp, shots

    Returns:
        Status string: "Yes", "Scaffold", "No", "Limited"
    """
    # Map dataset types to source attributes and fetch functions
    dataset_mapping = {
        "schedule": ("schedule_source", "fetch_schedule"),
        "player_game": ("box_score_source", "fetch_player_game"),
        "team_game": ("box_score_source", "fetch_team_game"),
        "player_season": ("player_season_source", "fetch_player_season"),
        "team_season": ("team_season_source", "fetch_team_season"),
        "pbp": ("pbp_source", "fetch_pbp"),
        "shots": ("shots_source", "fetch_shots"),
    }

    if dataset_type not in dataset_mapping:
        return "No"

    source_attr, fetch_attr = dataset_mapping[dataset_type]
    source = getattr(config, source_attr, "none")
    fetch_func = getattr(config, fetch_attr, None)

    # Determine status based on source and fetch function
    if source == "none":
        return "No"
    elif source in ["html_js"]:
        return "Scaffold"
    elif fetch_func is None and source not in [
        "espn",
        "euroleague_api",
        "nba_stats",
        "ceblpy",
        "html",
    ]:
        # For leagues that use generic aggregation
        if dataset_type in ["player_season", "team_season"]:
            # Check if they have box_score data
            if config.box_score_source != "none":
                return "Yes"
            return "Scaffold"
        return "Scaffold"
    elif "Scaffold" in config.notes or "scaffold" in config.notes.lower():
        # Check notes for scaffold indicators
        if (
            dataset_type == "team_season"
            and "team_season" in config.notes
            and "functional" in config.notes.lower()
        ):
            return "Yes"
        elif "404" in config.notes:
            return "Scaffold"

    # Special cases based on notes
    if config.league == "LNB_PROA":
        # LNB Pro A now has 7/7 datasets fully functional
        if dataset_type in [
            "schedule",
            "player_season",
            "team_season",
            "player_game",
            "team_game",
            "pbp",
            "shots",
        ]:
            return "Yes"
        return "No"
    elif config.league in ["NBL"]:
        if dataset_type in [
            "schedule",
            "player_season",
            "team_season",
            "player_game",
            "team_game",
            "pbp",
            "shots",
        ]:
            return "Yes"
        return "No"
    elif config.league in ["LKL", "BAL", "BCL", "ABA"]:
        if dataset_type in ["shots"]:
            return "No"
        return "Yes"
    elif config.league in ["USPORTS", "CCAA", "NAIA", "NJCAA"]:
        if dataset_type in ["pbp", "shots"]:
            return "No"
        return "Yes"
    elif config.league == "OTE":
        if dataset_type in ["shots"]:
            return "Limited"
        elif dataset_type == "pbp":
            return "Yes"
        return "Yes"
    elif config.league in ["CEBL"]:
        if dataset_type in ["pbp", "shots"]:
            return "No"
        return "Yes"
    elif config.league in ["NCAA-MBB", "NCAA-WBB", "EuroLeague", "EuroCup", "G-League", "WNBA"]:
        return "Yes"
    elif config.league == "ACB":
        return "Scaffold"

    # Default: if there's a fetch function or known source, assume Yes
    if fetch_func or source in ["espn", "euroleague_api", "nba_stats"]:
        return "Yes"

    return "No"


def get_historical_coverage(league: str, config) -> str:
    """Get historical data coverage for a league"""
    coverage_map = {
        "NCAA-MBB": "2002-present",
        "NCAA-WBB": "2005-present",
        "EuroLeague": "2001-present",
        "EuroCup": "2001-present",
        "G-League": "2001-present",
        "WNBA": "1997-present",
        "CEBL": "2019-present",
        "OTE": "2021-present",
        "NJCAA": "Current season",
        "NAIA": "Current season",
        "USPORTS": "Current season",
        "CCAA": "Current season",
        "NBL": "1979-present (schedule), 2015-present (detailed)",
        "NZ-NBL": "Current season (requires index)",
        "LKL": "Current season",
        "BAL": "Current season",
        "BCL": "Current season",
        "ABA": "Current season",
        "ACB": "Scaffold only",
        "LNB_PROA": "2021-present (box scores), 2025-2026 (PBP/shots)",
    }
    return coverage_map.get(league, "Unknown")


def get_data_source(config) -> str:
    """Get primary data source for a league"""
    source_map = {
        "espn": "ESPN API",
        "euroleague_api": "EuroLeague API",
        "nba_stats": "NBA Stats API",
        "ceblpy": "FIBA LiveStats (CEBLpy)",
        "html": "HTML Scraping",
        "html_js": "JS-Rendered (Selenium needed)",
        "fiba_html": "FIBA LiveStats HTML",
        "nbl_official_r": "nblR R Package",
        "nz_nbl_fiba": "FIBA LiveStats HTML",
        "prestosports": "PrestoSports Scraping",
        "lnb_api": "LNB Official API",
        "api_basketball": "API-Basketball",
        "none": "None",
    }

    # Get primary source
    primary = config.player_season_source
    return source_map.get(primary, primary)


def get_recency(league: str) -> str:
    """Get data recency for a league"""
    recency_map = {
        "NCAA-MBB": "Real-time (15-min delay)",
        "NCAA-WBB": "Real-time (15-min delay)",
        "EuroLeague": "Real-time",
        "EuroCup": "Real-time",
        "G-League": "Real-time (15-min delay)",
        "WNBA": "Real-time (15-min delay)",
        "CEBL": "Post-game",
        "OTE": "Post-game",
        "NJCAA": "Daily updates",
        "NAIA": "Daily updates",
        "USPORTS": "Post-game",
        "CCAA": "Post-game",
        "NBL": "Post-game",
        "NZ-NBL": "Post-game (manual index)",
        "LKL": "Post-game",
        "BAL": "Post-game",
        "BCL": "Post-game",
        "ABA": "Post-game",
        "ACB": "Scaffold only",
        "LNB_PROA": "Post-game",
    }
    return recency_map.get(league, "Unknown")


def generate_coverage_matrix():
    """Generate league coverage matrix"""
    # Register all sources
    _register_league_sources()

    print("\n" + "=" * 100)
    print("LEAGUE × DATASET AVAILABILITY MATRIX")
    print("=" * 100 + "\n")

    # Header
    datasets = [
        "schedule",
        "player_game",
        "team_game",
        "pbp",
        "shots",
        "player_season",
        "team_season",
    ]
    header = f"{'League':<20} | {'Level':<8} | " + " | ".join(f"{d:<14}" for d in datasets)
    print(header)
    print("-" * len(header))

    # Rows
    for league, config in sorted(LEAGUE_SOURCES.items()):
        level = LEAGUE_LEVELS.get(league, "UNKNOWN").upper()
        row = f"{league:<20} | {level:<8} | "

        statuses = []
        for dataset in datasets:
            status = get_dataset_status(config, dataset)
            statuses.append(f"{status:<14}")

        row += " | ".join(statuses)
        print(row)

    print("\n" + "=" * 100)
    print("HISTORICAL COVERAGE & RECENCY")
    print("=" * 100 + "\n")

    # Historical coverage table
    header2 = f"{'League':<20} | {'Historical Data':<30} | {'Recency':<30} | {'Data Source':<30}"
    print(header2)
    print("-" * len(header2))

    for league, config in sorted(LEAGUE_SOURCES.items()):
        coverage = get_historical_coverage(league, config)
        recency = get_recency(league)
        source = get_data_source(config)

        row = f"{league:<20} | {coverage:<30} | {recency:<30} | {source:<30}"
        print(row)

    print("\n" + "=" * 100)
    print("LEGEND")
    print("=" * 100 + "\n")
    print("- Yes: Full support with comprehensive data")
    print("- Limited: Partial support or limited data availability")
    print("- Scaffold: Infrastructure ready, returns empty DataFrames")
    print("- No: Not available for this league")
    print()


def generate_markdown_table():
    """Generate markdown table for README"""
    # Register all sources
    _register_league_sources()

    print("\n## League × Dataset Availability Matrix\n")

    datasets = [
        "schedule",
        "player_game",
        "team_game",
        "pbp",
        "shots",
        "player_season",
        "team_season",
    ]

    # Header
    print("| League | Level | " + " | ".join(datasets) + " |")
    print("|" + "|".join(["-" * len(d) for d in ["League", "Level"] + datasets]) + "|")

    # Rows
    for league, config in sorted(LEAGUE_SOURCES.items()):
        level = LEAGUE_LEVELS.get(league, "UNKNOWN").upper()

        statuses = []
        for dataset in datasets:
            status = get_dataset_status(config, dataset)
            statuses.append(status)

        row = f"| **{league}** | {level} | " + " | ".join(statuses) + " |"
        print(row)

    print("\n**Legend**:")
    print("- **Yes**: Full support with comprehensive data")
    print("- **Limited**: Partial support or limited data availability")
    print(
        "- **Scaffold**: Infrastructure ready, returns empty DataFrames (sites use JavaScript rendering; Selenium/Playwright required for actual data)"
    )
    print("- **No**: Not available for this league\n")

    print("\n## Historical Coverage & Recency\n")
    print("| League | Historical Data | Recency | Data Source |")
    print("|--------|----------------|---------|-------------|")

    for league, config in sorted(LEAGUE_SOURCES.items()):
        coverage = get_historical_coverage(league, config)
        recency = get_recency(league)
        source = get_data_source(config)

        row = f"| **{league}** | {coverage} | {recency} | {source} |"
        print(row)


if __name__ == "__main__":
    print("Generating League Coverage Matrix...\n")
    generate_coverage_matrix()
    print("\n" + "=" * 100)
    print("MARKDOWN TABLE FOR README")
    print("=" * 100)
    generate_markdown_table()
