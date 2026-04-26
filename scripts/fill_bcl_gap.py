#!/usr/bin/env python
# ruff: noqa: E402
"""Fill BCL gap for all available seasons (2016-2025).

This script fetches BCL (Basketball Champions League) player box score data
using the existing FIBA LiveStats fetcher infrastructure.

Target Seasons: 2016-17 through 2024-25
Validation Player: Alperen Sengun (played for Besiktas)

Usage:
    python scripts/fill_bcl_gap.py
    python scripts/fill_bcl_gap.py --seasons 2019-20 2020-21
    python scripts/fill_bcl_gap.py --dry-run
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Force unbuffered output
import functools

print = functools.partial(print, flush=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import time

import pandas as pd

# Import BCL fetcher with Playwright support
from cbb_data.fetchers.fiba_html_common import scrape_fiba_box_score

# BCL FIBA LiveStats constants
FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"
FIBA_LEAGUE_CODE = "BCL"
FIBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Rate limiting
RATE_LIMIT_DELAY = 0.5  # seconds between requests

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_PATH = DATA_DIR / "gold" / "player_career_game.parquet"
OUTPUT_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=BCL"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"

# All available BCL seasons
ALL_SEASONS = [
    "2016-17",
    "2017-18",
    "2018-19",
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
]

# Canonical schema columns
CANONICAL_SCHEMA = [
    "LEAGUE",
    "SEASON",
    "GAME_ID",
    "GAME_DATE",
    "SOURCE_PLAYER_ID",
    "PLAYER_NAME_RAW",
    "NAME_KEY",
    "TEAM_KEY",
    "TEAM_NAME_RAW",
    "IS_HOME",
    "OPPONENT_KEY",
    "MIN",
    "PTS",
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
    "TRB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "PLUS_MINUS",
    "STARTER",
    "DNP_REASON",
]


def fetch_schedule(season: str) -> pd.DataFrame:
    """Load BCL schedule from game index CSV."""
    index_file = GAME_INDEX_DIR / f"BCL_{season.replace('-', '_')}.csv"
    if not index_file.exists():
        return pd.DataFrame()
    return pd.read_csv(index_file)


def fetch_box_score(game_id: str, use_browser: bool = True) -> pd.DataFrame:
    """Fetch single game box score from FIBA LiveStats.

    Args:
        game_id: FIBA game ID
        use_browser: Use Playwright browser rendering to bypass 403 Forbidden (default: True)

    Returns:
        DataFrame with player box scores

    Note:
        BCL frequently blocks HTTP requests (403 Forbidden).
        Using use_browser=True (default) bypasses this restriction.
    """
    try:
        # Use shared FIBA scraper with Playwright support
        # This bypasses the 403 Forbidden error that BCL returns for HTTP requests
        df = scrape_fiba_box_score(
            league_code=FIBA_LEAGUE_CODE,
            game_id=str(game_id),
            league="BCL",
            season=None,  # Will be set by caller
            force_refresh=False,
            use_browser=use_browser,
        )

        if df.empty:
            return pd.DataFrame()

        # Rename columns to match expected format
        column_mapping = {
            "TEAM": "TEAM_NAME",
            "REB": "REB" if "REB" in df.columns else "TRB",
            "TRB": "REB",
            "TOV": "TO",
        }

        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]

        # Ensure GAME_ID is present
        df["GAME_ID"] = game_id

        return df

    except Exception as e:
        print(f"    ERROR fetching {game_id}: {e}")
        return pd.DataFrame()


def fetch_player_games_for_season(
    season: str, max_games: int = None, use_browser: bool = True
) -> pd.DataFrame:
    """Fetch all player-game data for a season.

    Args:
        season: Season string (e.g., "2023-24")
        max_games: Max games to fetch (for testing)
        use_browser: Use Playwright browser rendering to bypass 403 Forbidden (default: True)

    Returns:
        DataFrame with player-game data
    """
    schedule = fetch_schedule(season)
    if schedule.empty:
        return pd.DataFrame()

    if max_games:
        schedule = schedule.head(max_games)

    all_data = []
    errors = 0

    for idx, row in schedule.iterrows():
        game_id = str(row.get("GAME_ID", ""))
        if not game_id:
            continue

        time.sleep(RATE_LIMIT_DELAY)

        box = fetch_box_score(game_id, use_browser=use_browser)
        if not box.empty:
            # Add game metadata
            box["GAME_DATE"] = row.get("GAME_DATE")
            box["HOME_TEAM"] = row.get("HOME_TEAM")
            box["AWAY_TEAM"] = row.get("AWAY_TEAM")
            all_data.append(box)
        else:
            errors += 1

        if (idx + 1) % 20 == 0:
            print(f"    Processed {idx + 1}/{len(schedule)} games...")

    if errors > 0:
        print(f"    {errors} games failed to fetch")

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name."""
    if not name or pd.isna(name):
        return ""
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized


def transform_to_canonical(df: pd.DataFrame, season: str) -> pd.DataFrame:
    """Transform BCL fetcher output to canonical schema."""
    if df.empty:
        return pd.DataFrame()

    canonical = pd.DataFrame()

    # Basic identifiers
    canonical["LEAGUE"] = "BCL"
    canonical["SEASON"] = season

    # Map columns from fetcher output
    col_mapping = {
        "GAME_ID": "GAME_ID",
        "GAME_DATE": "GAME_DATE",
        "SOURCE_PLAYER_ID": "SOURCE_PLAYER_ID",
        "PLAYER_NAME": "PLAYER_NAME_RAW",
        "NAME_KEY": "NAME_KEY",
        "TEAM_NAME": "TEAM_NAME_RAW",
        "TEAM_KEY": "TEAM_KEY",
        "IS_HOME": "IS_HOME",
        "OPPONENT_NAME": "OPPONENT_KEY",
        "MIN": "MIN",
        "PTS": "PTS",
        "FGM": "FGM",
        "FGA": "FGA",
        "FG_PCT": "FG_PCT",
        "FG3M": "FG3M",
        "FG3A": "FG3A",
        "FG3_PCT": "FG3_PCT",
        "FTM": "FTM",
        "FTA": "FTA",
        "FT_PCT": "FT_PCT",
        "OREB": "OREB",
        "DREB": "DREB",
        "REB": "TRB",
        "AST": "AST",
        "STL": "STL",
        "BLK": "BLK",
        "TO": "TOV",
        "TOV": "TOV",
        "PF": "PF",
        "PLUS_MINUS": "PLUS_MINUS",
        "STARTER": "STARTER",
    }

    for src_col, dst_col in col_mapping.items():
        if src_col in df.columns and dst_col not in canonical.columns:
            canonical[dst_col] = df[src_col].values

    # Generate NAME_KEY if missing
    if "NAME_KEY" not in canonical.columns or canonical["NAME_KEY"].isna().all():
        if "PLAYER_NAME_RAW" in canonical.columns:
            canonical["NAME_KEY"] = canonical["PLAYER_NAME_RAW"].apply(normalize_name)
        elif "PLAYER_NAME" in df.columns:
            canonical["NAME_KEY"] = df["PLAYER_NAME"].apply(normalize_name)

    # Generate SOURCE_PLAYER_ID if missing
    if "SOURCE_PLAYER_ID" not in canonical.columns or canonical["SOURCE_PLAYER_ID"].isna().all():
        canonical["SOURCE_PLAYER_ID"] = [
            f"bcl:{season}:{name}" if name else None
            for name in canonical.get("NAME_KEY", [None] * len(canonical))
        ]

    # Add missing columns
    for col in CANONICAL_SCHEMA:
        if col not in canonical.columns:
            canonical[col] = None

    return canonical[CANONICAL_SCHEMA]


def validate_data(df: pd.DataFrame, season: str) -> dict:
    """Validate canonical data quality."""
    result = {
        "total_rows": len(df),
        "unique_games": df["GAME_ID"].nunique() if "GAME_ID" in df.columns else 0,
        "unique_players": df["NAME_KEY"].nunique() if "NAME_KEY" in df.columns else 0,
        "issues": [],
    }

    # Check PK uniqueness
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    available_pks = [c for c in pk_cols if c in df.columns]
    if available_pks:
        dupes = df.duplicated(subset=available_pks, keep=False).sum()
        if dupes > 0:
            result["issues"].append(f"{dupes} PK duplicates")

    # Check key columns
    if "NAME_KEY" in df.columns:
        name_coverage = df["NAME_KEY"].notna().mean()
        if name_coverage < 0.95:
            result["issues"].append(f"NAME_KEY coverage: {name_coverage:.1%}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Fill BCL gap for all seasons")
    parser.add_argument(
        "--seasons", nargs="+", default=ALL_SEASONS, help="Seasons to fetch (default: all)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't save to canonical directory")
    parser.add_argument(
        "--max-games", type=int, default=None, help="Max games per season (for testing)"
    )
    parser.add_argument(
        "--use-http",
        action="store_true",
        help="Try HTTP requests first (usually blocked with 403). Default: use Playwright",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("BCL GAP FILLER - Basketball Champions League")
    print("=" * 70)
    print(f"Seasons to fetch: {args.seasons}")
    print(
        f"Fetch method: {'HTTP (may fail with 403)' if args.use_http else 'Playwright (bypasses 403)'}"
    )
    print()

    all_data = []

    for season in args.seasons:
        print(f"\n{'=' * 50}")
        print(f"Processing {season}")
        print("=" * 50)

        # Check if game index exists
        index_file = GAME_INDEX_DIR / f"BCL_{season.replace('-', '_')}.csv"
        if not index_file.exists():
            print(f"  No game index found: {index_file}")
            continue

        # Load schedule and fetch box scores
        print("  Fetching player-game data...")
        try:
            use_browser = not args.use_http  # Default to Playwright unless --use-http specified
            player_games = fetch_player_games_for_season(
                season, args.max_games, use_browser=use_browser
            )
            print(f"    Fetched {len(player_games):,} player-game rows")
        except Exception as e:
            print(f"    ERROR fetching data: {e}")
            continue

        if player_games.empty:
            print(f"  No box score data for {season}")
            continue

        # Transform to canonical
        print("  Transforming to canonical schema...")
        canonical = transform_to_canonical(player_games, season)
        print(f"    Canonical rows: {len(canonical):,}")

        # Validate
        validation = validate_data(canonical, season)
        print(f"    Games: {validation['unique_games']}, Players: {validation['unique_players']}")
        if validation["issues"]:
            for issue in validation["issues"]:
                print(f"    WARN: {issue}")

        # Search for Alperen Sengun
        if "NAME_KEY" in canonical.columns:
            sengun = canonical[canonical["NAME_KEY"].str.contains("sengun", case=False, na=False)]
            if len(sengun) > 0:
                print(f"  [VALIDATION] Alperen Sengun: {len(sengun)} games")

        # Save canonical
        if not args.dry_run:
            output_dir = OUTPUT_DIR / f"season={season}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "data.parquet"
            canonical.to_parquet(output_path, index=False)
            print(f"  Saved: {output_path}")
        else:
            print(f"  [DRY RUN] Would save to {OUTPUT_DIR}/season={season}/data.parquet")

        all_data.append(canonical)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"Total rows: {len(combined):,}")
        print(f"Total games: {combined['GAME_ID'].nunique()}")
        print(f"Total players: {combined['NAME_KEY'].nunique()}")

        # Check for Sengun across all seasons
        sengun_total = combined[combined["NAME_KEY"].str.contains("sengun", case=False, na=False)]
        if len(sengun_total) > 0:
            print(f"\n[VALIDATION] Alperen Sengun total: {len(sengun_total)} games")
            print(f"  Seasons: {sengun_total['SEASON'].unique().tolist()}")
    else:
        print("No data fetched!")


if __name__ == "__main__":
    main()
