#!/usr/bin/env python
# ruff: noqa: E402
"""Fetch and Canonicalize FIBA League Data

For leagues using FIBA LiveStats (ABA, LKL, BCL, BAL, etc.), this script:
1. Fetches player_game data via FIBA HTML scraping
2. Joins with game index for dates
3. Canonicalizes to standard schema
4. Writes partitioned parquet files

Usage:
    python scripts/fetch_and_canonicalize_fiba.py --league ABA --season 2024-25
    python scripts/fetch_and_canonicalize_fiba.py --league LKL --seasons 2023-24,2022-23
    python scripts/fetch_and_canonicalize_fiba.py --league ABA --all-seasons
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pandas as pd

# Import league fetchers - use direct imports to avoid circular dependencies
FETCHERS = {}


def lazy_load_fetchers():
    """Lazy load fetchers to avoid circular import issues."""
    global FETCHERS
    if FETCHERS:
        return FETCHERS

    import importlib.util

    # Direct file imports to avoid __init__.py triggering circular imports
    fetchers_dir = PROJECT_ROOT / "src" / "cbb_data" / "fetchers"

    def load_module_directly(name: str, filepath: Path):
        """Load a module directly from file without package machinery."""
        spec = importlib.util.spec_from_file_location(name, filepath)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        return None

    # Load each fetcher directly from file
    for league, filename in [
        ("ABA", "aba.py"),
        ("LKL", "lkl.py"),
        ("BCL", "bcl.py"),
        ("BAL", "bal.py"),
    ]:
        filepath = fetchers_dir / filename
        if filepath.exists():
            try:
                module = load_module_directly(f"fetcher_{league}", filepath)
                if module and hasattr(module, "fetch_player_game"):
                    FETCHERS[league] = module
                    print(f"  Loaded {league} fetcher")
            except Exception as e:
                print(f"Warning: Could not import {league} fetcher: {e}")

    return FETCHERS


# Output directories
DATA_DIR = PROJECT_ROOT / "data"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game"

# Also check unified_basketball_mcp paths
UNIFIED_DATA_DIR = (
    PROJECT_ROOT.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp" / "data"
)
UNIFIED_INDEX_DIR = UNIFIED_DATA_DIR / "game_indexes"

CANONICAL_DIR.mkdir(parents=True, exist_ok=True)

# Canonical schema
CANONICAL_COLUMNS = [
    "LEAGUE",
    "SEASON",
    "GAME_ID",
    "GAME_DATE",
    "SOURCE_PLAYER_ID",
    "PLAYER_NAME_RAW",
    "NAME_KEY",
    "TEAM_NAME_RAW",
    "TEAM_KEY",
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
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "PLUS_MINUS",
]


def normalize_name(name: str | None) -> str:
    """Normalize player/team name to key format."""
    if not name or pd.isna(name):
        return ""

    name = str(name)
    # Normalize unicode (decompose accents)
    name = unicodedata.normalize("NFD", name)
    # Remove diacritics
    name = "".join(c for c in name if not unicodedata.combining(c))
    # Lowercase
    name = name.lower()
    # Remove punctuation except hyphens
    name = re.sub(r"[^\w\s-]", "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Replace spaces with underscores for key
    name_key = name.replace(" ", "_").replace("-", "_")
    return name_key


def load_game_index(league: str, season: str) -> pd.DataFrame:
    """Load game index for a league/season."""
    # Try various filename patterns
    season_formatted = season.replace("-", "_")
    patterns = [
        f"{league}_{season_formatted}.csv",
        f"{league}_{season}.csv",
    ]

    search_dirs = [GAME_INDEX_DIR, UNIFIED_INDEX_DIR]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for pattern in patterns:
            filepath = search_dir / pattern
            if filepath.exists():
                df = pd.read_csv(filepath)
                print(f"  Loaded game index: {filepath.name} ({len(df)} games)")
                return df

    print(f"  Warning: No game index found for {league} {season}")
    return pd.DataFrame()


def get_available_seasons(league: str) -> list[str]:
    """Get all seasons with game indexes for a league."""
    seasons = set()

    for search_dir in [GAME_INDEX_DIR, UNIFIED_INDEX_DIR]:
        if not search_dir.exists():
            continue
        for filepath in search_dir.glob(f"{league}_*.csv"):
            # Extract season from filename
            name = filepath.stem  # e.g., "ABA_2023_24"
            parts = name.replace(f"{league}_", "")  # e.g., "2023_24"
            season = parts.replace("_", "-")  # e.g., "2023-24"
            seasons.add(season)

    return sorted(seasons)


def canonicalize_fiba_data(
    df: pd.DataFrame, league: str, season: str, game_index: pd.DataFrame
) -> pd.DataFrame:
    """Transform FIBA fetcher output to canonical schema."""
    if df.empty:
        return df

    result = pd.DataFrame()

    # Identity columns
    result["LEAGUE"] = league
    result["SEASON"] = season

    # GAME_ID - try various column names
    for col in ["GAME_ID", "game_id", "GameID"]:
        if col in df.columns:
            result["GAME_ID"] = df[col].astype(str)
            break

    # SOURCE_PLAYER_ID
    for col in ["PLAYER_ID", "player_id", "PlayerID", "SOURCE_PLAYER_ID"]:
        if col in df.columns:
            result["SOURCE_PLAYER_ID"] = df[col].astype(str)
            break

    # Player name
    for col in ["PLAYER_NAME", "player_name", "PlayerName", "name"]:
        if col in df.columns:
            result["PLAYER_NAME_RAW"] = df[col]
            break

    if "PLAYER_NAME_RAW" in result.columns:
        result["NAME_KEY"] = result["PLAYER_NAME_RAW"].apply(normalize_name)

    # Team name
    for col in ["TEAM", "team", "TeamName", "TEAM_NAME"]:
        if col in df.columns:
            result["TEAM_NAME_RAW"] = df[col]
            break

    if "TEAM_NAME_RAW" in result.columns:
        result["TEAM_KEY"] = result["TEAM_NAME_RAW"].apply(normalize_name)

    # Stats columns - map various names
    stat_mappings = {
        "MIN": ["MIN", "min", "Minutes", "minutes_played"],
        "PTS": ["PTS", "pts", "Points", "points"],
        "REB": ["REB", "reb", "Rebounds", "rebounds_total"],
        "AST": ["AST", "ast", "Assists", "assists"],
        "STL": ["STL", "stl", "Steals", "steals"],
        "BLK": ["BLK", "blk", "Blocks", "blocks"],
        "TOV": ["TOV", "tov", "TO", "to", "Turnovers", "turnovers"],
        "PF": ["PF", "pf", "Fouls", "fouls_personal"],
        "FGM": ["FGM", "fgm", "FieldGoalsMade", "field_goals_made"],
        "FGA": ["FGA", "fga", "FieldGoalsAttempted", "field_goals_attempted"],
        "FG_PCT": ["FG_PCT", "fg_pct", "FieldGoalPct", "field_goal_percentage"],
        "FG3M": ["FG3M", "fg3m", "ThreePointersMade", "three_pointers_made"],
        "FG3A": ["FG3A", "fg3a", "ThreePointersAttempted", "three_pointers_attempted"],
        "FG3_PCT": ["FG3_PCT", "fg3_pct", "ThreePointPct", "three_pointer_percentage"],
        "FTM": ["FTM", "ftm", "FreeThrowsMade", "free_throws_made"],
        "FTA": ["FTA", "fta", "FreeThrowsAttempted", "free_throws_attempted"],
        "FT_PCT": ["FT_PCT", "ft_pct", "FreeThrowPct", "free_throw_percentage"],
        "OREB": ["OREB", "oreb", "OffensiveRebounds", "rebounds_offensive"],
        "DREB": ["DREB", "dreb", "DefensiveRebounds", "rebounds_defensive"],
        "PLUS_MINUS": ["PLUS_MINUS", "plus_minus", "PlusMinus"],
    }

    for canonical_col, source_cols in stat_mappings.items():
        for src_col in source_cols:
            if src_col in df.columns:
                result[canonical_col] = pd.to_numeric(df[src_col], errors="coerce")
                break

    # Join with game index for GAME_DATE
    if not game_index.empty and "GAME_ID" in result.columns:
        # Prepare game index
        game_index = game_index.copy()
        if "GAME_DATE" in game_index.columns:
            game_index["GAME_ID"] = game_index["GAME_ID"].astype(str)
            game_index_slim = game_index[["GAME_ID", "GAME_DATE"]].drop_duplicates()

            # Merge
            result = result.merge(game_index_slim, on="GAME_ID", how="left")
            date_coverage = result["GAME_DATE"].notna().mean() * 100
            print(f"  Date coverage after join: {date_coverage:.1f}%")

    # Ensure all canonical columns exist
    for col in CANONICAL_COLUMNS:
        if col not in result.columns:
            result[col] = None

    # Reorder columns
    result = result[CANONICAL_COLUMNS]

    return result


def validate_canonical(df: pd.DataFrame, league: str, season: str) -> dict:
    """Validate canonical data meets quality gates."""
    validation = {
        "league": league,
        "season": season,
        "rows": len(df),
        "gates": {},
        "status": "UNKNOWN",
    }

    # Gate 1: Primary key uniqueness
    key_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    available = [c for c in key_cols if c in df.columns and df[c].notna().any()]
    if available:
        dups = df.duplicated(subset=available, keep=False).sum()
        validation["gates"]["pk_unique"] = {
            "duplicates": int(dups),
            "status": "PASS" if dups == 0 else "FAIL",
        }

    # Gate 2: Shooting sanity (made <= attempted)
    shooting_errors = 0
    for made, att in [("FGM", "FGA"), ("FG3M", "FG3A"), ("FTM", "FTA")]:
        if made in df.columns and att in df.columns:
            mask = df[made].notna() & df[att].notna() & (df[made] > df[att])
            shooting_errors += mask.sum()
    validation["gates"]["shooting_sanity"] = {
        "errors": int(shooting_errors),
        "status": "PASS" if shooting_errors == 0 else "WARN",
    }

    # Gate 3: Date coverage
    if "GAME_DATE" in df.columns:
        date_coverage = df["GAME_DATE"].notna().mean() * 100
        validation["gates"]["date_coverage"] = {
            "pct": round(date_coverage, 1),
            "status": "PASS" if date_coverage >= 95 else "WARN",
        }

    # Gate 4: Name key coverage
    if "NAME_KEY" in df.columns:
        name_coverage = (df["NAME_KEY"] != "").mean() * 100
        validation["gates"]["name_coverage"] = {
            "pct": round(name_coverage, 1),
            "status": "PASS" if name_coverage >= 90 else "WARN",
        }

    # Overall status
    gate_statuses = [g.get("status", "UNKNOWN") for g in validation["gates"].values()]
    if "FAIL" in gate_statuses:
        validation["status"] = "FAIL"
    elif "WARN" in gate_statuses:
        validation["status"] = "WARN"
    else:
        validation["status"] = "PASS"

    return validation


def process_season(league: str, season: str, force_refresh: bool = False) -> dict:
    """Process a single league/season: fetch, canonicalize, validate, write."""
    print(f"\n{'='*60}")
    print(f"Processing {league} {season}")
    print("=" * 60)

    result = {
        "league": league,
        "season": season,
        "status": "UNKNOWN",
        "rows": 0,
        "validation": None,
        "output_path": None,
    }

    # Check if fetcher exists
    fetchers = lazy_load_fetchers()
    if league not in fetchers:
        print(f"  Error: No fetcher available for {league}")
        result["status"] = "ERROR"
        return result

    fetcher = fetchers[league]

    # Load game index
    game_index = load_game_index(league, season)

    # Fetch player_game data
    print("  Fetching player_game data from FIBA LiveStats...")
    try:
        df = fetcher.fetch_player_game(season=season, force_refresh=force_refresh)
        print(f"  Fetched {len(df)} player-game records")
    except Exception as e:
        print(f"  Error fetching data: {e}")
        result["status"] = "ERROR"
        return result

    if df.empty:
        print(f"  No data fetched for {league} {season}")
        result["status"] = "EMPTY"
        return result

    # Canonicalize
    print("  Canonicalizing...")
    canonical_df = canonicalize_fiba_data(df, league, season, game_index)
    print(f"  Canonicalized to {len(canonical_df)} rows")

    # Validate
    validation = validate_canonical(canonical_df, league, season)
    result["validation"] = validation
    result["rows"] = len(canonical_df)

    print(f"  Validation: {validation['status']}")
    for gate_name, gate_result in validation["gates"].items():
        print(f"    {gate_name}: {gate_result}")

    # Write output
    output_dir = CANONICAL_DIR / f"league={league}" / f"season={season}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "data.parquet"

    canonical_df.to_parquet(output_path, index=False)
    print(f"  Wrote: {output_path}")

    result["status"] = validation["status"]
    result["output_path"] = str(output_path)

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch and canonicalize FIBA league data")
    parser.add_argument("--league", required=True, help="League code (ABA, LKL, BCL, BAL)")
    parser.add_argument("--season", help="Single season (e.g., 2023-24)")
    parser.add_argument("--seasons", help="Comma-separated seasons (e.g., 2023-24,2022-23)")
    parser.add_argument("--all-seasons", action="store_true", help="Process all available seasons")
    parser.add_argument(
        "--force-refresh", action="store_true", help="Force re-fetch even if cached"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    league = args.league.upper()

    print("=" * 70)
    print("FIBA LEAGUE DATA FETCH AND CANONICALIZATION")
    print("=" * 70)
    print(f"League: {league}")
    fetchers = lazy_load_fetchers()
    print(f"Available fetchers: {list(fetchers.keys())}")
    print()

    # Determine seasons to process
    if args.all_seasons:
        seasons = get_available_seasons(league)
        print(f"All available seasons: {seasons}")
    elif args.seasons:
        seasons = [s.strip() for s in args.seasons.split(",")]
    elif args.season:
        seasons = [args.season]
    else:
        print("Error: Must specify --season, --seasons, or --all-seasons")
        return

    if args.dry_run:
        print(f"\nDry run - would process {len(seasons)} seasons: {seasons}")
        return

    # Process each season
    results = []
    for season in seasons:
        result = process_season(league, season, args.force_refresh)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for r in results:
        status_icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "ERROR": "✗", "EMPTY": "-"}.get(
            r["status"], "?"
        )
        print(f"  {status_icon} {r['league']} {r['season']}: {r['status']} ({r['rows']} rows)")

    total_rows = sum(r["rows"] for r in results)
    passed = sum(1 for r in results if r["status"] in ["PASS", "WARN"])
    print(f"\nTotal: {total_rows} rows across {len(results)} seasons ({passed} passed)")


if __name__ == "__main__":
    main()
