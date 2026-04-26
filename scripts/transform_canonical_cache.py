#!/usr/bin/env python
"""Transform Canonical Cache to Partitioned Format

Takes existing canonical cache files and writes them to the proper
partitioned structure: data/canonical/box_player_game/league=X/season=Y/data.parquet

Also generates a validation report showing which players are found.

Usage:
    python scripts/transform_canonical_cache.py
    python scripts/transform_canonical_cache.py --league NBL
    python scripts/transform_canonical_cache.py --validate-only
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game"
REPORTS_DIR = DATA_DIR / "_reports"

# Canonical cache locations
CACHE_DIRS = [
    PROJECT_ROOT.parent
    / "unified_basketball_mcp"
    / "servers"
    / "nba_prospects_mcp"
    / "cache"
    / "canonical",
    PROJECT_ROOT / "cache" / "canonical",
]

# Game index locations for date enrichment
GAME_INDEX_DIRS = [
    DATA_DIR / "game_indexes",
    PROJECT_ROOT.parent
    / "unified_basketball_mcp"
    / "servers"
    / "nba_prospects_mcp"
    / "data"
    / "game_indexes",
]

# Canonical schema columns
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

# Validation players to search for
VALIDATION_PLAYERS = {
    "alex_sarr": {
        "search": ["sarr", "alex"],
        "expected_leagues": ["OTE", "NBL"],
        "birth_year": 2005,
    },
    "luka_doncic": {
        "search": ["doncic"],
        "expected_leagues": ["ACB", "EUROLEAGUE"],
        "birth_year": 1999,
    },
    "nikola_jokic": {
        "search": ["jokic", "nikola"],
        "expected_leagues": ["ABA"],
        "birth_year": 1995,
    },
    "lamelo_ball": {"search": ["ball", "lamelo"], "expected_leagues": ["NBL"], "birth_year": 2001},
    "josh_giddey": {"search": ["giddey"], "expected_leagues": ["NBL"], "birth_year": 2002},
    "paolo_banchero": {
        "search": ["banchero"],
        "expected_leagues": ["NCAA_MBB"],
        "birth_year": 2002,
    },
    "victor_wembanyama": {
        "search": ["wembanyama"],
        "expected_leagues": ["LNB"],
        "birth_year": 2004,
    },
    "jalen_green": {
        "search": ["jalen green", "green, jalen"],
        "expected_leagues": ["G_LEAGUE"],
        "birth_year": 2002,
    },
}


def normalize_name(name):
    """Normalize name to key format."""
    if not name or pd.isna(name):
        return ""
    name = str(name)
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.replace(" ", "_").replace("-", "_")


def find_canonical_cache_files():
    """Find all canonical cache files."""
    files = {}
    for cache_dir in CACHE_DIRS:
        if not cache_dir.exists():
            continue
        for f in cache_dir.glob("*_combined_box_player_game.parquet"):
            if "raw" in f.name or "ALL_LEAGUES" in f.name:
                continue
            # Extract league from filename
            league = f.name.replace("_combined_box_player_game.parquet", "")
            if league not in files:
                files[league] = f
    return files


def load_game_indexes(league):
    """Load game index for date enrichment."""
    all_indexes = []
    league_upper = league.upper()

    for idx_dir in GAME_INDEX_DIRS:
        if not idx_dir.exists():
            continue
        for f in idx_dir.glob(f"{league_upper}_*.csv"):
            try:
                df = pd.read_csv(f)
                all_indexes.append(df)
            except Exception:
                continue

    if all_indexes:
        combined = pd.concat(all_indexes, ignore_index=True)
        if "GAME_ID" in combined.columns:
            combined["GAME_ID"] = combined["GAME_ID"].astype(str)
        return combined
    return pd.DataFrame()


def transform_to_canonical(df, league):
    """Transform cache data to canonical format."""
    result = pd.DataFrame()

    # LEAGUE
    result["LEAGUE"] = league.upper()

    # SEASON - try various columns
    for col in ["SEASON", "season", "Season"]:
        if col in df.columns:
            result["SEASON"] = df[col].astype(str)
            break

    # GAME_ID
    for col in ["GAME_ID", "game_id", "GameID", "match_id"]:
        if col in df.columns:
            result["GAME_ID"] = df[col].astype(str)
            break

    # SOURCE_PLAYER_ID
    for col in ["SOURCE_PLAYER_ID", "PLAYER_ID", "player_id", "PlayerID"]:
        if col in df.columns:
            result["SOURCE_PLAYER_ID"] = df[col].astype(str)
            break

    # Player name
    for col in ["PLAYER_NAME", "PLAYER_NAME_RAW", "player_name", "name"]:
        if col in df.columns:
            result["PLAYER_NAME_RAW"] = df[col]
            break

    if "PLAYER_NAME_RAW" in result.columns:
        result["NAME_KEY"] = result["PLAYER_NAME_RAW"].apply(normalize_name)

    # Team name
    for col in ["TEAM", "TEAM_NAME", "TEAM_NAME_RAW", "team", "team_name"]:
        if col in df.columns:
            result["TEAM_NAME_RAW"] = df[col]
            break

    if "TEAM_NAME_RAW" in result.columns:
        result["TEAM_KEY"] = result["TEAM_NAME_RAW"].apply(normalize_name)

    # Stats - map various column names
    stat_map = {
        "MIN": ["MIN", "min", "Minutes"],
        "PTS": ["PTS", "pts", "Points"],
        "REB": ["REB", "reb", "Rebounds"],
        "AST": ["AST", "ast", "Assists"],
        "STL": ["STL", "stl", "Steals"],
        "BLK": ["BLK", "blk", "Blocks"],
        "TOV": ["TOV", "tov", "TO", "Turnovers"],
        "PF": ["PF", "pf", "Fouls"],
        "FGM": ["FGM", "fgm"],
        "FGA": ["FGA", "fga"],
        "FG_PCT": ["FG_PCT", "fg_pct"],
        "FG3M": ["FG3M", "fg3m"],
        "FG3A": ["FG3A", "fg3a"],
        "FG3_PCT": ["FG3_PCT", "fg3_pct"],
        "FTM": ["FTM", "ftm"],
        "FTA": ["FTA", "fta"],
        "FT_PCT": ["FT_PCT", "ft_pct"],
        "OREB": ["OREB", "oreb"],
        "DREB": ["DREB", "dreb"],
        "PLUS_MINUS": ["PLUS_MINUS", "plus_minus"],
    }

    for canonical_col, source_cols in stat_map.items():
        for src in source_cols:
            if src in df.columns:
                result[canonical_col] = pd.to_numeric(df[src], errors="coerce")
                break

    # Ensure all columns exist
    for col in CANONICAL_COLUMNS:
        if col not in result.columns:
            result[col] = None

    return result[CANONICAL_COLUMNS]


def search_validation_players(df, league):
    """Search for validation players in dataframe."""
    results = {}

    name_col = None
    for col in ["NAME_KEY", "PLAYER_NAME_RAW", "PLAYER_NAME", "name"]:
        if col in df.columns:
            name_col = col
            break

    if not name_col:
        return results

    for player_key, info in VALIDATION_PLAYERS.items():
        if league.upper() not in [lg.upper() for lg in info["expected_leagues"]]:
            continue

        for term in info["search"]:
            matches = df[df[name_col].str.lower().str.contains(term, na=False)]
            if len(matches) > 0:
                seasons = matches["SEASON"].unique().tolist() if "SEASON" in matches.columns else []
                results[player_key] = {
                    "found": True,
                    "games": len(matches),
                    "seasons": seasons,
                    "league": league.upper(),
                }
                break

    return results


def write_partitioned(df, league):
    """Write canonical data partitioned by league/season."""
    if df.empty or "SEASON" not in df.columns:
        return []

    written = []
    for season in df["SEASON"].unique():
        season_df = df[df["SEASON"] == season]

        # Normalize season format for directory
        season_str = str(season).replace("/", "-")

        output_dir = CANONICAL_DIR / f"league={league.upper()}" / f"season={season_str}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "data.parquet"
        season_df.to_parquet(output_path, index=False)

        written.append(
            {
                "league": league.upper(),
                "season": season_str,
                "rows": len(season_df),
                "path": str(output_path),
            }
        )
        print(f"  Wrote {len(season_df)} rows to {output_path.relative_to(PROJECT_ROOT)}")

    return written


def main():
    parser = argparse.ArgumentParser(description="Transform canonical cache")
    parser.add_argument("--league", help="Process specific league only")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't write")
    args = parser.parse_args()

    print("=" * 70)
    print("CANONICAL CACHE TRANSFORMATION")
    print("=" * 70)
    print()

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Find cache files
    cache_files = find_canonical_cache_files()
    print(f"Found {len(cache_files)} canonical cache files:")
    for league, path in cache_files.items():
        print(f"  {league}: {path.name}")
    print()

    # Filter by league if specified
    if args.league:
        league_upper = args.league.upper()
        cache_files = {k: v for k, v in cache_files.items() if k.upper() == league_upper}

    # Process each league
    all_results = []
    all_validation = {}

    for league, filepath in cache_files.items():
        print(f"\n{'='*50}")
        print(f"Processing {league}")
        print("=" * 50)

        # Load cache
        df = pd.read_parquet(filepath)
        print(f"Loaded {len(df)} rows")

        # Transform
        canonical_df = transform_to_canonical(df, league)
        print(f"Transformed to {len(canonical_df)} canonical rows")

        # Try to enrich with dates from game index
        game_index = load_game_indexes(league)
        if (
            not game_index.empty
            and "GAME_DATE" in game_index.columns
            and "GAME_ID" in game_index.columns
        ):
            if "GAME_ID" in canonical_df.columns:
                # Deduplicate game index first
                game_dates = game_index[["GAME_ID", "GAME_DATE"]].drop_duplicates(
                    subset=["GAME_ID"], keep="first"
                )
                rows_before = len(canonical_df)
                canonical_df = canonical_df.merge(
                    game_dates, on="GAME_ID", how="left", suffixes=("", "_idx")
                )
                if "GAME_DATE_idx" in canonical_df.columns:
                    canonical_df["GAME_DATE"] = canonical_df["GAME_DATE"].fillna(
                        canonical_df["GAME_DATE_idx"]
                    )
                    canonical_df.drop(columns=["GAME_DATE_idx"], inplace=True)

                # Deduplicate result if join created duplicates
                if len(canonical_df) > rows_before:
                    key_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
                    available_keys = [c for c in key_cols if c in canonical_df.columns]
                    canonical_df = canonical_df.drop_duplicates(subset=available_keys, keep="first")
                    print(f"  (Deduplicated from {rows_before} to {len(canonical_df)} rows)")

                date_coverage = canonical_df["GAME_DATE"].notna().mean() * 100
                print(f"Date coverage after enrichment: {date_coverage:.1f}%")

        # Search for validation players
        validation = search_validation_players(canonical_df, league)
        if validation:
            print("Validation players found:")
            for player, info in validation.items():
                print(f"  {player}: {info['games']} games in seasons {info['seasons']}")
            all_validation.update(validation)

        # Write partitioned output
        if not args.validate_only:
            written = write_partitioned(canonical_df, league)
            all_results.extend(written)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all_results:
        total_rows = sum(r["rows"] for r in all_results)
        print(f"\nWrote {total_rows} rows across {len(all_results)} league-seasons:")
        for r in all_results:
            print(f"  {r['league']} {r['season']}: {r['rows']} rows")

    print(f"\nValidation Players Found: {len(all_validation)}/{len(VALIDATION_PLAYERS)}")
    for player, info in all_validation.items():
        print(f"  {player}: {info['league']} - {info['games']} games")

    # Missing validation players
    found_players = set(all_validation.keys())
    missing = set(VALIDATION_PLAYERS.keys()) - found_players
    if missing:
        print(f"\nMissing validation players ({len(missing)}):")
        for player in missing:
            info = VALIDATION_PLAYERS[player]
            print(f"  {player}: expected in {info['expected_leagues']}")

    # Save report
    report = {
        "transformed": all_results,
        "validation": all_validation,
        "missing_players": list(missing),
    }
    report_path = REPORTS_DIR / "canonical_transform_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
