#!/usr/bin/env python
"""Fill G-League gap for missing seasons (2021-22, 2023-24, 2024-25).

This script fetches G-League player box score data for missing seasons
using the NBA Stats API (G-League endpoint) and merges it with the existing
gold table.

Usage:
    python scripts/fill_gleague_gap.py
    python scripts/fill_gleague_gap.py --seasons 2023-24 2024-25
    python scripts/fill_gleague_gap.py --dry-run
"""

import argparse
import hashlib
import re
import sys
import time
import unicodedata
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import requests

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_PATH = DATA_DIR / "gold" / "player_career_game.parquet"
OUTPUT_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=G_LEAGUE"

# G League API base URL and headers
GLEAGUE_BASE_URL = "https://stats.gleague.nba.com/stats"
GLEAGUE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://stats.gleague.nba.com/",
    "Origin": "https://stats.gleague.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

# Seasons to fill
MISSING_SEASONS = ["2021-22", "2023-24", "2024-25"]


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


def generate_canonical_id(name_key: str, source_id: str, league: str = "G_LEAGUE") -> str:
    """Generate deterministic canonical player ID."""
    base = f"{league}_{name_key}_{source_id}"
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:8]
    return f"P_{name_key[:20]}_{hash_suffix}"


def _make_gleague_request(endpoint: str, params: dict) -> dict:
    """Make a request to the G League Stats API."""
    url = f"{GLEAGUE_BASE_URL}/{endpoint}"

    try:
        response = requests.get(url, headers=GLEAGUE_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: G League API request failed: {url} - {e}")
        return {}


def _parse_resultset(data: dict, result_set_name: str = None) -> pd.DataFrame:
    """Parse G League API ResultSet into DataFrame."""
    if "resultSets" not in data:
        return pd.DataFrame()

    result_set = None
    for rs in data["resultSets"]:
        if result_set_name and rs.get("name", "").lower() == result_set_name.lower():
            result_set = rs
            break

    if result_set is None and data["resultSets"]:
        result_set = data["resultSets"][0]

    if result_set is None:
        return pd.DataFrame()

    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])

    if not headers or not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=headers)


def fetch_gleague_player_game_log(season: str) -> pd.DataFrame:
    """Fetch all player game logs for a G-League season.

    This uses leaguegamelog endpoint which returns one row per player per game.
    """
    print(f"  Fetching player game logs for {season}...")

    params = {
        "LeagueID": "20",  # G League
        "Season": season,
        "SeasonType": "Regular Season",
        "PlayerOrTeam": "P",  # Player stats
        "Counter": 0,
        "Sorter": "DATE",
        "Direction": "ASC",
    }

    data = _make_gleague_request("leaguegamelog", params)
    df = _parse_resultset(data, "LeagueGameLog")

    if df.empty:
        print(f"    No data found for {season}")
        return df

    print(f"    Found {len(df):,} player-game rows")
    return df


def fetch_gleague_schedule(season: str) -> pd.DataFrame:
    """Fetch G-League schedule for a season."""
    print(f"  Fetching schedule for {season}...")

    params = {
        "LeagueID": "20",
        "Season": season,
        "SeasonType": "Regular Season",
    }

    data = _make_gleague_request("leaguegamefinder", params)
    df = _parse_resultset(data, "LeagueGameFinderResults")

    if df.empty:
        print(f"    No schedule found for {season}")
        return df

    print(f"    Found {len(df):,} team-game rows")
    return df


def transform_to_canonical(df: pd.DataFrame, season: str) -> pd.DataFrame:
    """Transform G-League game log to canonical schema."""
    if df.empty:
        return pd.DataFrame()

    # Map G-League API columns to canonical schema
    # The leaguegamelog returns these columns:
    # SEASON_ID, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME,
    # GAME_ID, GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT,
    # FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS, PLUS_MINUS

    # Create DataFrame with explicit size to avoid index alignment issues
    n_rows = len(df)
    canonical = pd.DataFrame(index=range(n_rows))

    # Basic identifiers - use lists/Series with correct length
    canonical["LEAGUE"] = ["G_LEAGUE"] * n_rows
    canonical["SEASON"] = [str(season)] * n_rows
    canonical["GAME_ID"] = df["GAME_ID"].astype(str).values
    canonical["SOURCE_PLAYER_ID"] = df["PLAYER_ID"].astype(str).values
    canonical["PLAYER_NAME_RAW"] = df["PLAYER_NAME"].values
    canonical["NAME_KEY"] = df["PLAYER_NAME"].apply(normalize_name).values

    # Team info
    canonical["TEAM_KEY"] = df["TEAM_ABBREVIATION"].values
    team_name = df.get("TEAM_NAME", df["TEAM_ABBREVIATION"])
    canonical["TEAM_NAME_RAW"] = team_name.values if hasattr(team_name, "values") else team_name

    # Parse MATCHUP to get opponent and home/away
    # Format: "BIR @ MEM" (away) or "MEM vs. BIR" (home)
    def parse_matchup(matchup, team):
        if pd.isna(matchup):
            return None, False
        matchup = str(matchup)
        if " @ " in matchup:
            # Away game: TEAM @ OPPONENT
            parts = matchup.split(" @ ")
            opponent = parts[1] if len(parts) > 1 else None
            is_home = False
        elif " vs. " in matchup:
            # Home game: TEAM vs. OPPONENT
            parts = matchup.split(" vs. ")
            opponent = parts[1] if len(parts) > 1 else None
            is_home = True
        else:
            opponent = None
            is_home = False
        return opponent, is_home

    matchup_info = df.apply(
        lambda x: parse_matchup(x.get("MATCHUP"), x.get("TEAM_ABBREVIATION")), axis=1
    )
    canonical["OPPONENT_KEY"] = [m[0] for m in matchup_info]
    canonical["IS_HOME"] = [m[1] for m in matchup_info]

    # Game date
    canonical["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce").values

    # Stats - map directly
    stat_columns = {
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
        "REB": "TRB",  # Total rebounds
        "AST": "AST",
        "STL": "STL",
        "BLK": "BLK",
        "TOV": "TOV",
        "PF": "PF",
        "PLUS_MINUS": "PLUS_MINUS",
    }

    for src_col, dst_col in stat_columns.items():
        if src_col in df.columns:
            canonical[dst_col] = pd.to_numeric(df[src_col], errors="coerce")
        else:
            canonical[dst_col] = None

    # Add REB as TRB if not present
    if "TRB" not in canonical.columns or canonical["TRB"].isna().all():
        if "REB" in df.columns:
            canonical["TRB"] = pd.to_numeric(df["REB"], errors="coerce").values

    # Calculate REB from OREB + DREB if TRB is missing
    if "TRB" not in canonical.columns or canonical["TRB"].isna().all():
        canonical["TRB"] = (canonical["OREB"].fillna(0) + canonical["DREB"].fillna(0)).values

    # Generate canonical player ID
    canonical_ids = [
        generate_canonical_id(nk, sp)
        for nk, sp in zip(canonical["NAME_KEY"], canonical["SOURCE_PLAYER_ID"], strict=False)
    ]
    canonical["CANONICAL_PLAYER_ID"] = canonical_ids

    # Metadata
    canonical["SOURCE"] = ["gleague_api"] * n_rows
    canonical["STARTER"] = [None] * n_rows  # Not available in game log
    canonical["DNP_REASON"] = [None] * n_rows

    # These will be computed when merging to gold
    canonical["CAREER_GAME_NUMBER"] = [None] * n_rows
    canonical["LEAGUE_GAME_NUMBER"] = [None] * n_rows
    canonical["PLAYER_UID"] = [None] * n_rows
    canonical["CONFIDENCE"] = [1.0] * n_rows

    return canonical


def validate_data(df: pd.DataFrame, season: str) -> bool:
    """Validate the canonical data meets quality gates."""
    if df.empty:
        print(f"  WARN: No data for {season}")
        return False

    # Check PK uniqueness
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    pk_dupes = df.duplicated(subset=pk_cols, keep=False).sum()
    if pk_dupes > 0:
        print(f"  FAIL: {pk_dupes} PK duplicates in {season}")
        return False

    # Check stat sanity
    if "FGM" in df.columns and "FGA" in df.columns:
        invalid_fg = (df["FGM"].fillna(0) > df["FGA"].fillna(0)).sum()
        if invalid_fg > 0:
            print(f"  WARN: {invalid_fg} rows with FGM > FGA")

    if "FG3M" in df.columns and "FG3A" in df.columns:
        invalid_fg3 = (df["FG3M"].fillna(0) > df["FG3A"].fillna(0)).sum()
        if invalid_fg3 > 0:
            print(f"  WARN: {invalid_fg3} rows with FG3M > FG3A")

    # Check NAME_KEY coverage
    name_coverage = df["NAME_KEY"].notna().mean()
    if name_coverage < 0.9:
        print(f"  WARN: NAME_KEY coverage only {name_coverage:.1%}")

    # Check GAME_DATE coverage
    date_coverage = df["GAME_DATE"].notna().mean()
    if date_coverage < 0.95:
        print(f"  WARN: GAME_DATE coverage only {date_coverage:.1%}")

    print(f"  PASS: {len(df):,} rows, {df['NAME_KEY'].nunique()} unique players")
    return True


def merge_to_gold(new_data: pd.DataFrame, dry_run: bool = False) -> pd.DataFrame:
    """Merge new G-League data with existing gold table."""
    if not GOLD_PATH.exists():
        print(f"ERROR: Gold table not found at {GOLD_PATH}")
        return pd.DataFrame()

    print("\nLoading existing gold table...")
    gold = pd.read_parquet(GOLD_PATH)
    print(f"  Existing rows: {len(gold):,}")

    # Remove existing G-League data for the seasons we're replacing
    seasons_to_add = new_data["SEASON"].unique()
    mask = ~((gold["LEAGUE"] == "G_LEAGUE") & (gold["SEASON"].isin(seasons_to_add)))
    gold_filtered = gold[mask].copy()
    print(f"  After removing existing seasons {list(seasons_to_add)}: {len(gold_filtered):,}")

    # Ensure columns match
    gold_cols = set(gold.columns)
    new_cols = set(new_data.columns)

    # Add missing columns to new_data
    for col in gold_cols - new_cols:
        new_data[col] = None

    # Select only columns that exist in gold
    new_data = new_data[[c for c in gold.columns if c in new_data.columns]]

    # Concatenate
    merged = pd.concat([gold_filtered, new_data], ignore_index=True)

    # Recompute game numbers
    print("  Recomputing game numbers...")
    merged = merged.sort_values(["NAME_KEY", "GAME_DATE"])
    merged["CAREER_GAME_NUMBER"] = merged.groupby("NAME_KEY").cumcount() + 1
    merged["LEAGUE_GAME_NUMBER"] = merged.groupby(["NAME_KEY", "LEAGUE"]).cumcount() + 1

    print(f"  Final gold rows: {len(merged):,}")

    if not dry_run:
        print(f"\nSaving to {GOLD_PATH}...")
        merged.to_parquet(GOLD_PATH, index=False)
        print("  Done!")
    else:
        print("\n[DRY RUN] Would save to gold table")

    return merged


def main():
    parser = argparse.ArgumentParser(description="Fill G-League gap for missing seasons")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=MISSING_SEASONS,
        help="Seasons to fetch (default: 2021-22 2023-24 2024-25)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't save to gold table")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR),
        help="Output directory for canonical files",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("G-LEAGUE GAP FILLER")
    print("=" * 70)
    print(f"Seasons to fetch: {args.seasons}")
    print()

    all_data = []

    for season in args.seasons:
        print(f"\n{'=' * 50}")
        print(f"Processing {season}")
        print("=" * 50)

        # Fetch data
        df = fetch_gleague_player_game_log(season)

        if df.empty:
            print(f"  Skipping {season} - no data")
            continue

        # Transform to canonical
        print("  Transforming to canonical schema...")
        canonical = transform_to_canonical(df, season)

        # Validate
        print("  Validating...")
        if not validate_data(canonical, season):
            print(f"  Skipping {season} - validation failed")
            continue

        # Save canonical file
        output_dir = Path(args.output_dir) / f"season={season}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "data.parquet"

        if not args.dry_run:
            canonical.to_parquet(output_path, index=False)
            print(f"  Saved canonical: {output_path}")
        else:
            print(f"  [DRY RUN] Would save to {output_path}")

        all_data.append(canonical)

        # Rate limit
        time.sleep(1.0)

    if not all_data:
        print("\nNo data fetched!")
        return

    # Combine all seasons
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal new data: {len(combined):,} rows")

    # Merge to gold
    merge_to_gold(combined, dry_run=args.dry_run)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for season in args.seasons:
        season_data = combined[combined["SEASON"] == season]
        print(f"  {season}: {len(season_data):,} rows, {season_data['NAME_KEY'].nunique()} players")


if __name__ == "__main__":
    main()
