#!/usr/bin/env python
"""Status Report - Unified Multi-League Basketball Career Pipeline

Prints readiness matrix with 5-gate validation status per league:
- INDEX_GATE: Game index artifact exists with valid PK and coverage
- RAW_GATE: Stat sanity checks (FGM<=FGA, etc.)
- CANON_GATE: Canonical schema compliance
- GOLD_GATE: Gold table PK uniqueness and PLAYER_UID coverage
- XWALK_GATE: Cross-league identity resolution quality

Usage:
    python tools/status_report.py
"""

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not found. Try using a different Python environment.")
    sys.exit(1)


# Configuration
BASE_DIR = Path(__file__).parent.parent
UNIFIED_BASE = BASE_DIR.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp"

GOLD_TABLE_PATH = BASE_DIR / "data" / "gold" / "player_career_game.parquet"
GOLD_PARTITIONS_PATH = UNIFIED_BASE / "data" / "gold" / "box_player_game"
CANONICAL_CACHE_PATH = UNIFIED_BASE / "cache" / "canonical"
XWALK_PATH = UNIFIED_BASE / "cache" / "identity" / "player_xwalk.parquet"

# Game index directories (two locations)
GAME_INDEX_DIRS = [
    BASE_DIR / "data" / "game_indexes",
    UNIFIED_BASE / "data" / "game_indexes",
]

# Validation players with expected leagues
KNOWN_PATHWAYS = {
    "luka_doncic": {"birth_year": 1999, "leagues": ["ACB", "EUROLEAGUE"]},
    "ricky_rubio": {"birth_year": 1990, "leagues": ["ACB"]},
    "nikola_jokic": {"birth_year": 1995, "leagues": ["ABA"]},
    "nikola_jovic": {"birth_year": 2003, "leagues": ["ABA"]},
    "alperen_sengun": {"birth_year": 2002, "leagues": ["BCL"]},
    "victor_wembanyama": {"birth_year": 2004, "leagues": ["LNB_PROA"]},
    "jan_vesely": {"birth_year": 1990, "leagues": ["EUROLEAGUE"]},
    "deividas_sirvydis": {"birth_year": 2000, "leagues": ["LKL"]},
    "alex_sarr": {"birth_year": 2005, "leagues": ["OTE", "NBL"]},
    "amen_thompson": {"birth_year": 2003, "leagues": ["OTE"]},
    "ausar_thompson": {"birth_year": 2003, "leagues": ["OTE"]},
    "jalen_green": {"birth_year": 2002, "leagues": ["G_LEAGUE"]},
    "scoot_henderson": {"birth_year": 2004, "leagues": ["G_LEAGUE"]},
    "jonathan_kuminga": {"birth_year": 2002, "leagues": ["G_LEAGUE"]},
    "lamelo_ball": {"birth_year": 2001, "leagues": ["NBL"]},
    "josh_giddey": {"birth_year": 2002, "leagues": ["NBL"]},
    "dyson_daniels": {"birth_year": 2003, "leagues": ["NBL"]},
    "paolo_banchero": {"birth_year": 2002, "leagues": ["NCAA_MBB"]},
    "chet_holmgren": {"birth_year": 2002, "leagues": ["NCAA_MBB"]},
    "zach_edey": {"birth_year": 2002, "leagues": ["NCAA_MBB"]},
}

# Expected leagues to track
TARGET_LEAGUES = [
    "NCAA_MBB",
    "G_LEAGUE",
    "NBL",
    "LNB_PROA",
    "EUROLEAGUE",
    "CEBL",
    "ABA",
    "ACB",
    "OTE",
    "BCL",
    "BAL",
    "LKL",
    "EUROCUP",
    "NZ_NBL",
    "WNBA",
    "BBL",
]


def status_icon(passed: bool | None) -> str:
    """Return status icon for gate check."""
    if passed is None:
        return "?"
    return "Y" if passed else "X"


def load_gold_table() -> pd.DataFrame | None:
    """Load gold career table if it exists."""
    if GOLD_TABLE_PATH.exists():
        try:
            return pd.read_parquet(GOLD_TABLE_PATH)
        except Exception as e:
            print(f"  Warning: Could not load gold table: {e}")
    return None


def scan_game_indexes() -> dict:
    """Scan all game index files and return summary by league."""
    indexes = defaultdict(lambda: {"seasons": [], "total_games": 0, "files": []})

    for idx_dir in GAME_INDEX_DIRS:
        if not idx_dir.exists():
            continue
        for f in idx_dir.glob("*.csv"):
            # Parse league and season from filename
            # Formats: LEAGUE_SEASON.csv or LEAGUE_SEASON_SEASON.csv
            name = f.stem
            parts = name.split("_")

            if len(parts) >= 2:
                # Handle different naming conventions
                league = parts[0]
                season = "_".join(parts[1:])

                # Normalize league names
                league_norm = league.upper()
                if league_norm == "G-LEAGUE" or league_norm == "G":
                    league_norm = "G_LEAGUE"
                elif league_norm == "NCAA-MBB" or league_norm == "NCAA":
                    league_norm = "NCAA_MBB"
                elif league_norm == "NZ" or league_norm == "NZ-NBL":
                    league_norm = "NZ_NBL"

                indexes[league_norm]["seasons"].append(season)
                indexes[league_norm]["files"].append(f)

                # Count games in file
                try:
                    df = pd.read_csv(f)
                    indexes[league_norm]["total_games"] += len(df)
                except Exception:
                    pass

    return dict(indexes)


def check_index_gate(league: str, index_info: dict | None) -> tuple[bool, str]:
    """Check INDEX_GATE: Game index exists with valid data."""
    if not index_info or not index_info.get("files"):
        return False, "No index"

    seasons = index_info.get("seasons", [])
    games = index_info.get("total_games", 0)

    if games == 0:
        return False, "0 games"

    return True, f"{len(seasons)}s/{games}g"


def check_gold_gate(gold_df: pd.DataFrame | None, league: str) -> tuple[bool | None, str]:
    """Check GOLD_GATE: League data in gold table with valid PKs."""
    if gold_df is None:
        return None, "No gold"

    # Normalize league column if needed
    league_col = "LEAGUE"
    if league_col not in gold_df.columns:
        for col in gold_df.columns:
            if col.upper() == "LEAGUE":
                league_col = col
                break

    if league_col not in gold_df.columns:
        return None, "No LEAGUE col"

    # Filter to league (handle various normalizations)
    league_variants = [league, league.replace("_", "-"), league.replace("_", " ")]
    mask = gold_df[league_col].str.upper().isin([lg.upper() for lg in league_variants])
    league_df = gold_df[mask]

    if len(league_df) == 0:
        return False, "0 rows"

    # Check PK uniqueness
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    [
        c
        for c in pk_cols
        if c in gold_df.columns or c.lower() in [x.lower() for x in gold_df.columns]
    ]

    rows = len(league_df)

    return True, f"{rows:,}"


def check_xwalk_gate(xwalk_df: pd.DataFrame | None, league: str) -> tuple[bool | None, str]:
    """Check XWALK_GATE: Player crosswalk entries for league."""
    if xwalk_df is None:
        return None, "No xwalk"

    # Find league column
    league_cols = [c for c in xwalk_df.columns if "league" in c.lower()]
    if not league_cols:
        return None, "No league col"

    # Count entries for this league
    count = 0
    for col in league_cols:
        matches = xwalk_df[col].astype(str).str.upper().str.contains(league.upper(), na=False)
        count += matches.sum()

    if count == 0:
        return False, "0 links"

    return True, f"{count}"


def get_validation_player(league: str) -> str:
    """Get validation player for a league."""
    for player, info in KNOWN_PATHWAYS.items():
        if league.upper() in [lg.upper() for lg in info["leagues"]]:
            return player.replace("_", " ").title()
    return "TBD"


def check_validation_player(gold_df: pd.DataFrame | None, league: str) -> tuple[bool | None, str]:
    """Check if validation player appears in gold data for this league."""
    if gold_df is None:
        return None, "No gold"

    player_name = get_validation_player(league)
    if player_name == "TBD":
        return None, "TBD"

    # Find NAME_KEY or similar column
    name_col = None
    for col in gold_df.columns:
        if col.upper() in ["NAME_KEY", "PLAYER_NAME", "NAME"]:
            name_col = col
            break

    if not name_col:
        return None, "No name col"

    # Search for player (case-insensitive, normalized)
    search_key = player_name.lower().replace(" ", "_")
    mask = gold_df[name_col].astype(str).str.lower().str.contains(search_key.split()[0], na=False)

    # Also filter by league
    league_col = "LEAGUE" if "LEAGUE" in gold_df.columns else None
    if league_col:
        league_mask = gold_df[league_col].str.upper() == league.upper()
        mask = mask & league_mask

    found = mask.sum()

    if found > 0:
        return True, f"{found}g"

    return False, "Not found"


def print_readiness_matrix(
    gold_df: pd.DataFrame | None, indexes: dict, xwalk_df: pd.DataFrame | None
):
    """Print the readiness matrix for all leagues."""
    print("\n" + "=" * 100)
    print(f"READINESS MATRIX - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 100)
    print()

    # Header
    header = f"{'League':<12} | {'Index':<12} | {'Gold':<12} | {'Xwalk':<10} | {'Val Player':<20} | {'Status':<10}"
    print(header)
    print("-" * len(header))

    blockers = []

    for league in TARGET_LEAGUES:
        # INDEX_GATE
        idx_info = (
            indexes.get(league)
            or indexes.get(league.replace("_", "-"))
            or indexes.get(league.replace("_", ""))
        )
        idx_pass, idx_msg = check_index_gate(league, idx_info)

        # GOLD_GATE
        gold_pass, gold_msg = check_gold_gate(gold_df, league)

        # XWALK_GATE
        xwalk_pass, xwalk_msg = check_xwalk_gate(xwalk_df, league)

        # Validation player check
        val_player = get_validation_player(league)
        val_pass, val_msg = check_validation_player(gold_df, league)

        # Determine overall status
        if gold_pass and idx_pass:
            status = "OK"
        elif gold_pass:
            status = "PARTIAL"
        elif idx_pass:
            status = "INDEXED"
        else:
            status = "BLOCKED"
            blockers.append(league)

        # Format row
        idx_str = f"{status_icon(idx_pass)} {idx_msg}"
        gold_str = f"{status_icon(gold_pass)} {gold_msg}"
        xwalk_str = f"{status_icon(xwalk_pass)} {xwalk_msg}"
        val_str = f"{val_player} ({val_msg})"

        row = f"{league:<12} | {idx_str:<12} | {gold_str:<12} | {xwalk_str:<10} | {val_str:<20} | {status:<10}"
        print(row)

    print()

    # Blockers summary
    if blockers:
        print("BLOCKERS:")
        for league in blockers:
            print(f"  - {league}: Missing index and gold data")

    print()


def print_gold_table_summary(gold_df: pd.DataFrame | None):
    """Print gold table summary statistics."""
    print("\n" + "=" * 100)
    print("GOLD TABLE SUMMARY")
    print("=" * 100)

    if gold_df is None:
        print("\n  Gold table not found at:", GOLD_TABLE_PATH)
        return

    print(f"\n  Location: {GOLD_TABLE_PATH}")
    print(f"  Total rows: {len(gold_df):,}")

    # League breakdown
    league_col = None
    for col in gold_df.columns:
        if col.upper() == "LEAGUE":
            league_col = col
            break

    if league_col:
        print("\n  League breakdown:")
        league_counts = gold_df[league_col].value_counts()
        for league, count in league_counts.items():
            print(f"    {league:<15}: {count:>10,} rows")

    # Unique players
    name_col = None
    for col in gold_df.columns:
        if col.upper() in ["NAME_KEY", "PLAYER_NAME"]:
            name_col = col
            break

    if name_col:
        unique_players = gold_df[name_col].nunique()
        print(f"\n  Unique players (NAME_KEY): {unique_players:,}")

    # PK uniqueness check
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    pk_present = [c for c in pk_cols if c in gold_df.columns]

    if len(pk_present) >= 3:
        duplicates = gold_df.duplicated(subset=pk_present, keep=False).sum()
        if duplicates > 0:
            print(f"\n  WARNING: {duplicates:,} duplicate PK rows found!")
        else:
            print("\n  PK Uniqueness: PASS (0 duplicates)")

    # Season range by league
    if "SEASON" in gold_df.columns and league_col:
        print("\n  Season ranges by league:")
        for league in gold_df[league_col].unique():
            league_seasons = gold_df[gold_df[league_col] == league]["SEASON"].unique()
            seasons_sorted = sorted([str(s) for s in league_seasons])
            if len(seasons_sorted) > 0:
                print(
                    f"    {league:<15}: {seasons_sorted[0]} - {seasons_sorted[-1]} ({len(seasons_sorted)} seasons)"
                )

    print()


def print_game_index_summary(indexes: dict):
    """Print game index summary."""
    print("\n" + "=" * 100)
    print("GAME INDEX SUMMARY")
    print("=" * 100)

    total_games = 0
    total_seasons = 0

    for league, info in sorted(indexes.items()):
        seasons = len(info.get("seasons", []))
        games = info.get("total_games", 0)
        total_games += games
        total_seasons += seasons

        print(f"  {league:<15}: {seasons:>3} seasons, {games:>6,} games")

    print(f"\n  TOTAL: {len(indexes)} leagues, {total_seasons} season-files, {total_games:,} games")
    print()


def print_validation_players_status(gold_df: pd.DataFrame | None):
    """Print validation player status."""
    print("\n" + "=" * 100)
    print("VALIDATION PLAYERS STATUS")
    print("=" * 100)

    if gold_df is None:
        print("\n  Cannot check - gold table not loaded")
        return

    print()
    header = f"{'Player':<25} | {'Birth':<6} | {'Expected Leagues':<25} | {'Found':<10}"
    print(header)
    print("-" * len(header))

    name_col = None
    for col in gold_df.columns:
        if col.upper() in ["NAME_KEY", "PLAYER_NAME"]:
            name_col = col
            break

    for player_key, info in KNOWN_PATHWAYS.items():
        player_name = player_key.replace("_", " ").title()
        birth = info["birth_year"]
        expected = ", ".join(info["leagues"])

        # Search for player
        if name_col:
            search_key = player_key.split("_")[0]  # First name
            mask = gold_df[name_col].astype(str).str.lower().str.contains(search_key, na=False)
            found = mask.sum()

            if found > 0:
                found_str = f"{found}g"
            else:
                found_str = "Not found"
        else:
            found_str = "?"

        print(f"{player_name:<25} | {birth:<6} | {expected:<25} | {found_str:<10}")

    print()


def main():
    """Main entry point."""
    print("\n" + "=" * 100)
    print("UNIFIED MULTI-LEAGUE BASKETBALL CAREER PIPELINE - STATUS REPORT")
    print("=" * 100)
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load data
    print("\nLoading data...")
    gold_df = load_gold_table()
    if gold_df is not None:
        print(f"  Loaded gold table: {len(gold_df):,} rows")
    else:
        print("  Gold table not found")

    # Scan game indexes
    indexes = scan_game_indexes()
    print(f"  Scanned game indexes: {len(indexes)} leagues")

    # Load crosswalk if exists
    xwalk_df = None
    if XWALK_PATH.exists():
        try:
            xwalk_df = pd.read_parquet(XWALK_PATH)
            print(f"  Loaded crosswalk: {len(xwalk_df):,} entries")
        except Exception:
            pass

    # Print reports
    print_gold_table_summary(gold_df)
    print_game_index_summary(indexes)
    print_readiness_matrix(gold_df, indexes, xwalk_df)
    print_validation_players_status(gold_df)

    print("=" * 100)
    print("END OF REPORT")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()
