#!/usr/bin/env python
"""Canonicalize box_player_game Data (Phase 3)

Transforms raw box score data from each league into a unified canonical schema.
Ensures consistent column naming, data types, and validation across all leagues.

Canonical Schema Invariants:
- LEAGUE, SEASON, GAME_ID, GAME_DATE (from game index)
- SOURCE_PLAYER_ID (nullable if not available)
- PLAYER_NAME_RAW, NAME_KEY (normalized)
- TEAM_NAME_RAW, TEAM_KEY (normalized)
- Core stats: MIN, PTS, REB, AST, STL, BLK, TOV, PF
- Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
- Rebounds: OREB, DREB
- PLUS_MINUS

Gate Requirements:
- No duplicate (LEAGUE, SEASON, GAME_ID, TEAM_KEY, SOURCE_PLAYER_ID) keys
- Numeric columns are actually numeric
- made <= attempted for all shooting stats

Usage:
    python scripts/canonicalize_player_game.py
    python scripts/canonicalize_player_game.py --league NBL
    python scripts/canonicalize_player_game.py --validate-only
"""

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd

# Constants
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
NBL_RAW_DIR = DATA_DIR / "nbl_raw"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game"
REPORTS_DIR = DATA_DIR / "_reports"
VALIDATION_DIR = DATA_DIR / "_validation"

CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

# Canonical schema definition
CANONICAL_SCHEMA = {
    # Identity columns
    "LEAGUE": "string",
    "SEASON": "string",
    "GAME_ID": "string",
    "GAME_DATE": "string",
    "SOURCE_PLAYER_ID": "string",
    "PLAYER_NAME_RAW": "string",
    "NAME_KEY": "string",
    "TEAM_NAME_RAW": "string",
    "TEAM_KEY": "string",
    # Time
    "MIN": "float64",
    # Core stats
    "PTS": "float64",
    "REB": "float64",
    "AST": "float64",
    "STL": "float64",
    "BLK": "float64",
    "TOV": "float64",
    "PF": "float64",
    # Shooting
    "FGM": "float64",
    "FGA": "float64",
    "FG_PCT": "float64",
    "FG3M": "float64",
    "FG3A": "float64",
    "FG3_PCT": "float64",
    "FTM": "float64",
    "FTA": "float64",
    "FT_PCT": "float64",
    # Rebounds breakdown
    "OREB": "float64",
    "DREB": "float64",
    # Plus/minus
    "PLUS_MINUS": "float64",
}

# Column mapping for different source formats
NBL_COLUMN_MAP = {
    # Player identity
    "player_id": "SOURCE_PLAYER_ID",
    "player_name": "PLAYER_NAME_RAW",
    "first_name": "_first_name",
    "family_name": "_family_name",
    "jersey_number": "_jersey_number",
    # Team
    "team_id": "_source_team_id",
    "team_name": "TEAM_NAME_RAW",
    "opp_team_id": "_opp_team_id",
    "opp_team_name": "_opp_team_name",
    # Game
    "match_id": "GAME_ID",
    "season": "SEASON",
    "match_time": "_match_time",
    "round": "_round",
    # Stats
    "minutes_played": "MIN",
    "points": "PTS",
    "rebounds_total": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TOV",
    "fouls_personal": "PF",
    "field_goals_made": "FGM",
    "field_goals_attempted": "FGA",
    "field_goal_percentage": "FG_PCT",
    "three_pointers_made": "FG3M",
    "three_pointers_attempted": "FG3A",
    "three_pointer_percentage": "FG3_PCT",
    "free_throws_made": "FTM",
    "free_throws_attempted": "FTA",
    "free_throw_percentage": "FT_PCT",
    "rebounds_offensive": "OREB",
    "rebounds_defensive": "DREB",
    "plus_minus": "PLUS_MINUS",
}


def normalize_name(name: str | None) -> str:
    """Normalize player/team name to key format.

    Removes accents, lowercases, removes punctuation, collapses whitespace.
    """
    if not name or pd.isna(name):
        return ""

    # Convert to string
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


def parse_minutes(value) -> float | None:
    """Parse minutes from various formats (MM:SS, decimal, etc)."""
    if pd.isna(value):
        return None

    if isinstance(value, int | float):
        return float(value)

    value_str = str(value).strip()

    # Format: "MM:SS"
    if ":" in value_str:
        parts = value_str.split(":")
        try:
            minutes = int(parts[0])
            seconds = int(parts[1]) if len(parts) > 1 else 0
            return minutes + seconds / 60.0
        except (ValueError, IndexError):
            pass

    # Try direct float conversion
    try:
        return float(value_str)
    except ValueError:
        return None


def validate_shooting_stats(df: pd.DataFrame) -> list[str]:
    """Validate that made <= attempted for all shooting stats."""
    errors = []

    shooting_pairs = [
        ("FGM", "FGA"),
        ("FG3M", "FG3A"),
        ("FTM", "FTA"),
    ]

    for made_col, attempted_col in shooting_pairs:
        if made_col in df.columns and attempted_col in df.columns:
            mask = (
                df[made_col].notna()
                & df[attempted_col].notna()
                & (df[made_col] > df[attempted_col])
            )
            if mask.any():
                count = mask.sum()
                errors.append(f"{count} rows where {made_col} > {attempted_col}")

    return errors


def validate_canonical_data(df: pd.DataFrame, league: str) -> dict:
    """Run validation gates on canonical data."""
    validation = {
        "league": league,
        "total_rows": len(df),
        "gates": {},
        "errors": [],
        "warnings": [],
        "status": "UNKNOWN",
    }

    # Gate 1: Primary key uniqueness
    key_cols = ["LEAGUE", "SEASON", "GAME_ID", "TEAM_KEY", "SOURCE_PLAYER_ID"]
    available_keys = [c for c in key_cols if c in df.columns and df[c].notna().any()]

    if available_keys:
        duplicates = df.duplicated(subset=available_keys, keep=False)
        dup_count = duplicates.sum()
        validation["gates"]["uniqueness"] = {
            "key_columns": available_keys,
            "duplicates": int(dup_count),
            "status": "PASS" if dup_count == 0 else "FAIL",
        }
        if dup_count > 0:
            validation["errors"].append(f"{dup_count} duplicate primary key rows")

    # Gate 2: Numeric columns are numeric
    numeric_cols = [c for c, t in CANONICAL_SCHEMA.items() if t == "float64"]
    non_numeric = []
    for col in numeric_cols:
        if col in df.columns:
            try:
                pd.to_numeric(df[col], errors="raise")
            except (ValueError, TypeError):
                non_numeric.append(col)

    validation["gates"]["numeric_types"] = {
        "checked": numeric_cols,
        "non_numeric": non_numeric,
        "status": "PASS" if not non_numeric else "FAIL",
    }
    if non_numeric:
        validation["errors"].append(f"Non-numeric values in: {non_numeric}")

    # Gate 3: Shooting stats sanity
    shooting_errors = validate_shooting_stats(df)
    validation["gates"]["shooting_sanity"] = {
        "errors": shooting_errors,
        "status": "PASS" if not shooting_errors else "WARN",
    }
    if shooting_errors:
        validation["warnings"].extend(shooting_errors)

    # Gate 4: Required columns present
    required = ["LEAGUE", "SEASON", "GAME_ID", "PLAYER_NAME_RAW"]
    missing = [c for c in required if c not in df.columns or df[c].isna().all()]
    validation["gates"]["required_columns"] = {
        "required": required,
        "missing": missing,
        "status": "PASS" if not missing else "FAIL",
    }
    if missing:
        validation["errors"].append(f"Missing required columns: {missing}")

    # Gate 5: NAME_KEY populated
    if "NAME_KEY" in df.columns:
        name_key_coverage = df["NAME_KEY"].notna().mean() * 100
        validation["gates"]["name_key_coverage"] = {
            "coverage_pct": round(name_key_coverage, 1),
            "status": "PASS" if name_key_coverage > 95 else "WARN",
        }

    # Determine overall status
    gate_statuses = [g.get("status", "UNKNOWN") for g in validation["gates"].values()]
    if "FAIL" in gate_statuses:
        validation["status"] = "FAIL"
    elif "WARN" in gate_statuses:
        validation["status"] = "WARN"
    elif gate_statuses:
        validation["status"] = "PASS"

    return validation


def canonicalize_nbl(game_index_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Canonicalize NBL box score data.

    Args:
        game_index_df: Optional game index for joining dates

    Returns:
        Canonical DataFrame
    """
    box_path = NBL_RAW_DIR / "nbl_box_player.parquet"

    if not box_path.exists():
        print(f"NBL box player data not found: {box_path}")
        return pd.DataFrame()

    print(f"Loading NBL box player data from {box_path}")
    df = pd.read_parquet(box_path)
    print(f"Loaded {len(df)} rows")
    print(f"Columns: {list(df.columns)}")

    # Add LEAGUE
    df["LEAGUE"] = "NBL"

    # Create PLAYER_NAME_RAW from first_name + family_name
    if "first_name" in df.columns and "family_name" in df.columns:
        df["PLAYER_NAME_RAW"] = df["first_name"].fillna("") + " " + df["family_name"].fillna("")
        df["PLAYER_NAME_RAW"] = df["PLAYER_NAME_RAW"].str.strip()
    elif "name" in df.columns:
        df["PLAYER_NAME_RAW"] = df["name"]

    # Create NAME_KEY
    df["NAME_KEY"] = df["PLAYER_NAME_RAW"].apply(normalize_name)

    # Create TEAM_NAME_RAW and TEAM_KEY
    if "team_name" in df.columns:
        df["TEAM_NAME_RAW"] = df["team_name"]
        df["TEAM_KEY"] = df["TEAM_NAME_RAW"].apply(normalize_name)

    # Create SOURCE_PLAYER_ID - use player_id if available, otherwise create composite
    if "player_id" in df.columns and df["player_id"].notna().any():
        # Use player_id where available
        df["SOURCE_PLAYER_ID"] = df["player_id"].astype(str)
        # For null player_ids, create composite from name + team
        mask = df["SOURCE_PLAYER_ID"].isin(["None", "nan", ""])
        df.loc[mask, "SOURCE_PLAYER_ID"] = df.loc[mask, "NAME_KEY"] + "_" + df.loc[mask, "TEAM_KEY"]
    else:
        # Create composite player ID from name + team
        df["SOURCE_PLAYER_ID"] = df["NAME_KEY"] + "_" + df["TEAM_KEY"]

    # Map GAME_ID from match_id
    if "match_id" in df.columns:
        df["GAME_ID"] = df["match_id"].astype(str)

    # Map SEASON
    if "season" in df.columns:
        df["SEASON"] = df["season"]

    # Parse minutes
    if "minutes" in df.columns:
        df["MIN"] = df["minutes"].apply(parse_minutes)

    # Map stats columns
    stat_mapping = {
        "points": "PTS",
        "rebounds_total": "REB",
        "assists": "AST",
        "steals": "STL",
        "blocks": "BLK",
        "turnovers": "TOV",
        "fouls_personal": "PF",
        "field_goals_made": "FGM",
        "field_goals_attempted": "FGA",
        "field_goals_percentage": "FG_PCT",
        "three_pointers_made": "FG3M",
        "three_pointers_attempted": "FG3A",
        "three_pointers_percentage": "FG3_PCT",
        "free_throws_made": "FTM",
        "free_throws_attempted": "FTA",
        "free_throws_percentage": "FT_PCT",
        "rebounds_offensive": "OREB",
        "rebounds_defensive": "DREB",
        "plus_minus": "PLUS_MINUS",
    }
    for src, dst in stat_mapping.items():
        if src in df.columns:
            df[dst] = df[src]

    # Join with game index to get dates
    if game_index_df is not None and "GAME_ID" in df.columns:
        # Filter to NBL games
        nbl_index = game_index_df[game_index_df["LEAGUE"] == "NBL"].copy()
        if not nbl_index.empty:
            date_df = nbl_index[["GAME_ID", "GAME_DATE"]].drop_duplicates()
            date_df["GAME_ID"] = date_df["GAME_ID"].astype(str)
            df = df.merge(date_df, on="GAME_ID", how="left")
            print(
                f"Joined with game index, date coverage: {df['GAME_DATE'].notna().mean()*100:.1f}%"
            )

    # Deduplicate on primary key
    key_cols = ["LEAGUE", "SEASON", "GAME_ID", "TEAM_KEY", "SOURCE_PLAYER_ID"]
    before_dedup = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    after_dedup = len(df)
    if before_dedup != after_dedup:
        print(
            f"Deduplicated: {before_dedup} -> {after_dedup} rows (removed {before_dedup - after_dedup})"
        )

    # Select and order canonical columns
    canonical_cols = list(CANONICAL_SCHEMA.keys())
    available_cols = [c for c in canonical_cols if c in df.columns]

    result = df[available_cols].copy()

    # Add missing columns as None
    for col in canonical_cols:
        if col not in result.columns:
            result[col] = None

    # Reorder to canonical order
    result = result[canonical_cols]

    print(f"Canonicalized {len(result)} NBL player-game rows")

    return result


def canonicalize_league(league: str, game_index_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Canonicalize data for a specific league."""
    if league == "NBL":
        return canonicalize_nbl(game_index_df)
    else:
        # For other leagues, look for raw box score data
        raw_path = RAW_DIR / league.lower() / "box_player.parquet"
        if not raw_path.exists():
            print(f"No raw box data found for {league} at {raw_path}")
            return pd.DataFrame()

        print(f"Loading {league} raw data from {raw_path}")
        df = pd.read_parquet(raw_path)

        # Apply generic transformations (can be expanded per-league)
        df["LEAGUE"] = league

        # Try to find player name columns
        name_cols = [c for c in df.columns if "player" in c.lower() and "name" in c.lower()]
        if name_cols:
            df["PLAYER_NAME_RAW"] = df[name_cols[0]]
            df["NAME_KEY"] = df["PLAYER_NAME_RAW"].apply(normalize_name)

        # Try to find team name columns
        team_cols = [c for c in df.columns if "team" in c.lower() and "name" in c.lower()]
        if team_cols:
            df["TEAM_NAME_RAW"] = df[team_cols[0]]
            df["TEAM_KEY"] = df["TEAM_NAME_RAW"].apply(normalize_name)

        # Select canonical columns
        canonical_cols = list(CANONICAL_SCHEMA.keys())
        available_cols = [c for c in canonical_cols if c in df.columns]

        result = df[available_cols].copy()

        for col in canonical_cols:
            if col not in result.columns:
                result[col] = None

        return result[canonical_cols]


def load_game_indexes() -> pd.DataFrame:
    """Load all game indexes into a single DataFrame."""
    all_indexes = []

    for filepath in sorted(GAME_INDEX_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(filepath)
            all_indexes.append(df)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    if all_indexes:
        return pd.concat(all_indexes, ignore_index=True)
    return pd.DataFrame()


def write_canonical_parquet(df: pd.DataFrame, league: str, season: str | None = None):
    """Write canonical data to partitioned parquet."""
    if df.empty:
        print(f"No data to write for {league}")
        return None

    # Output path based on league and season
    if season:
        output_dir = CANONICAL_DIR / f"league={league}" / f"season={season}"
    else:
        output_dir = CANONICAL_DIR / f"league={league}"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Write parquet
    output_path = output_dir / "data.parquet"
    df.to_parquet(output_path, index=False)

    print(f"Wrote {len(df)} rows to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Canonicalize box_player_game data")
    parser.add_argument("--league", help="Specific league to process (default: all available)")
    parser.add_argument(
        "--validate-only", action="store_true", help="Only validate existing canonical data"
    )
    parser.add_argument("--output", help="Override output directory")
    args = parser.parse_args()

    print("=" * 70)
    print("BOX PLAYER GAME CANONICALIZATION (Phase 3)")
    print("=" * 70)
    print()

    if args.validate_only:
        print("Running validation only...")
        # Validate existing canonical data
        for league_dir in CANONICAL_DIR.glob("league=*"):
            league = league_dir.name.replace("league=", "")
            print(f"\nValidating {league}...")

            for parquet_file in league_dir.rglob("*.parquet"):
                df = pd.read_parquet(parquet_file)
                validation = validate_canonical_data(df, league)

                print(f"  {parquet_file.name}: {validation['status']}")
                print(f"    Rows: {validation['total_rows']}")

                for gate_name, gate_result in validation["gates"].items():
                    print(f"    {gate_name}: {gate_result['status']}")

                # Save validation report
                report_path = VALIDATION_DIR / f"{league}_canonical_validation.json"
                with open(report_path, "w") as f:
                    json.dump(validation, f, indent=2)

        return

    # Load game indexes for date joining
    print("Loading game indexes...")
    game_index_df = load_game_indexes()
    print(f"Loaded {len(game_index_df)} game index records")
    print()

    # Determine which leagues to process
    if args.league:
        leagues = [args.league.upper()]
    else:
        # Check which leagues have raw data
        leagues = []
        if (NBL_RAW_DIR / "nbl_box_player.parquet").exists():
            leagues.append("NBL")
        for raw_league_dir in RAW_DIR.glob("*"):
            if raw_league_dir.is_dir() and (raw_league_dir / "box_player.parquet").exists():
                leagues.append(raw_league_dir.name.upper())

    print(f"Leagues to process: {leagues}")
    print()

    all_validations = {}

    for league in leagues:
        print(f"\n{'='*50}")
        print(f"Processing {league}")
        print("=" * 50)

        # Filter game index for this league
        league_index = (
            game_index_df[game_index_df["LEAGUE"] == league] if not game_index_df.empty else None
        )

        # Canonicalize
        canonical_df = canonicalize_league(league, league_index)

        if canonical_df.empty:
            print(f"No data produced for {league}")
            continue

        # Validate
        print(f"\nValidating {league} canonical data...")
        validation = validate_canonical_data(canonical_df, league)
        all_validations[league] = validation

        print(f"  Status: {validation['status']}")
        print(f"  Rows: {validation['total_rows']}")

        for gate_name, gate_result in validation["gates"].items():
            status = gate_result.get("status", "UNKNOWN")
            print(f"  {gate_name}: {status}")

        if validation["errors"]:
            print(f"  Errors: {validation['errors']}")
        if validation["warnings"]:
            print(f"  Warnings: {validation['warnings']}")

        # Write canonical data if validation passes
        if validation["status"] in ["PASS", "WARN"]:
            # Group by season and write partitioned
            if "SEASON" in canonical_df.columns:
                for season in canonical_df["SEASON"].unique():
                    season_df = canonical_df[canonical_df["SEASON"] == season]
                    write_canonical_parquet(season_df, league, str(season))
            else:
                write_canonical_parquet(canonical_df, league)
        else:
            print(f"Skipping write for {league} due to validation failures")

    # Save overall report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "leagues_processed": leagues,
        "validations": all_validations,
    }

    report_path = (
        REPORTS_DIR / f"canonicalization_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved report to: {report_path}")

    # Print summary
    print("\n" + "=" * 70)
    print("CANONICALIZATION SUMMARY")
    print("=" * 70)

    for league, validation in all_validations.items():
        print(f"{league}: {validation['status']} ({validation['total_rows']} rows)")


if __name__ == "__main__":
    main()
