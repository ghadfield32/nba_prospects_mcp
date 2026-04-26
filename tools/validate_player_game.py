#!/usr/bin/env python
"""5-Gate Validation for Player Game Data

Validates data for a specific league and season against 5 gates:
- INDEX_GATE: Game index artifact exists with valid PK and coverage
- RAW_GATE: Stat sanity checks (FGM<=FGA, etc.)
- CANON_GATE: Canonical schema compliance
- GOLD_GATE: Gold table PK uniqueness
- XWALK_GATE: Cross-league identity resolution quality

Usage:
    python tools/validate_player_game.py --league NBL --season 2023-24
    python tools/validate_player_game.py --league ABA --all-seasons
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not found.")
    sys.exit(1)


# Configuration
BASE_DIR = Path(__file__).parent.parent
UNIFIED_BASE = BASE_DIR.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp"

GOLD_TABLE_PATH = BASE_DIR / "data" / "gold" / "player_career_game.parquet"
GOLD_PARTITIONS_PATH = UNIFIED_BASE / "data" / "gold" / "box_player_game"
CANONICAL_PATH = UNIFIED_BASE / "data" / "canonical" / "box_player_game"
CANONICAL_CACHE_PATH = UNIFIED_BASE / "cache" / "canonical"

GAME_INDEX_DIRS = [
    BASE_DIR / "data" / "game_indexes",
    UNIFIED_BASE / "data" / "game_indexes",
]

# Canonical schema columns
CANONICAL_COLUMNS = [
    "LEAGUE",
    "SEASON",
    "GAME_ID",
    "GAME_DATE",
    "TEAM_KEY",
    "SOURCE_PLAYER_ID",
    "PLAYER_NAME_RAW",
    "NAME_KEY",
    "OPPONENT_KEY",
    "IS_HOME",
    "MIN",
    "PTS",
    "FGM",
    "FGA",
    "FG3M",
    "FG3A",
    "FTM",
    "FTA",
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
    "SOURCE",
]

# Required columns (must have data)
REQUIRED_COLUMNS = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID", "PTS"]


@dataclass
class GateResult:
    """Result of a gate check."""

    passed: bool
    message: str
    details: dict | None = None


@dataclass
class ValidationResult:
    """Complete validation result for a league/season."""

    league: str
    season: str
    index_gate: GateResult
    raw_gate: GateResult
    canon_gate: GateResult
    gold_gate: GateResult
    xwalk_gate: GateResult

    @property
    def all_passed(self) -> bool:
        return all(
            [
                self.index_gate.passed,
                self.raw_gate.passed,
                self.canon_gate.passed,
                self.gold_gate.passed,
                self.xwalk_gate.passed,
            ]
        )

    def print_report(self):
        """Print validation report."""
        status = "PASS" if self.all_passed else "FAIL"
        print(f"\n{'='*60}")
        print(f"VALIDATION: {self.league} {self.season} - {status}")
        print(f"{'='*60}")

        gates = [
            ("INDEX_GATE", self.index_gate),
            ("RAW_GATE", self.raw_gate),
            ("CANON_GATE", self.canon_gate),
            ("GOLD_GATE", self.gold_gate),
            ("XWALK_GATE", self.xwalk_gate),
        ]

        for name, result in gates:
            icon = "PASS" if result.passed else "FAIL"
            print(f"  {name:<12}: [{icon}] {result.message}")
            if result.details and not result.passed:
                for k, v in result.details.items():
                    print(f"    - {k}: {v}")

        print()


def normalize_league(league: str) -> str:
    """Normalize league name."""
    norm = league.upper().replace("-", "_").replace(" ", "_")
    if norm == "G_LEAGUE":
        return "G_LEAGUE"
    if norm == "NCAA" or norm == "NCAA_MBB":
        return "NCAA_MBB"
    return norm


def normalize_season(season: str) -> str:
    """Normalize season format (2023_2024 -> 2023-2024)."""
    return season.replace("_", "-")


def season_matches(s1: str, s2: str) -> bool:
    """Check if two season strings match after normalization."""
    return normalize_season(str(s1)) == normalize_season(str(s2))


def find_game_index(league: str, season: str) -> Path | None:
    """Find game index file for league/season."""
    league_norm = normalize_league(league)

    # Try different filename patterns
    patterns = [
        f"{league_norm}_{season}.csv",
        f"{league_norm}_{season.replace('-', '_')}.csv",
        f"{league}_{season}.csv",
        f"{league}_{season.replace('-', '_')}.csv",
    ]

    for idx_dir in GAME_INDEX_DIRS:
        if not idx_dir.exists():
            continue
        for pattern in patterns:
            path = idx_dir / pattern
            if path.exists():
                return path

    # Try glob matching
    for idx_dir in GAME_INDEX_DIRS:
        if not idx_dir.exists():
            continue
        matches = list(idx_dir.glob(f"{league_norm}*{season}*.csv"))
        if matches:
            return matches[0]

    return None


def check_index_gate(league: str, season: str) -> GateResult:
    """Check INDEX_GATE for a league/season."""
    idx_path = find_game_index(league, season)

    if not idx_path:
        return GateResult(passed=False, message=f"No index file found for {league} {season}")

    try:
        df = pd.read_csv(idx_path)
    except Exception as e:
        return GateResult(passed=False, message=f"Failed to read index: {e}")

    details = {"file": str(idx_path), "rows": len(df)}

    # Check required columns
    required = ["GAME_ID"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return GateResult(passed=False, message=f"Missing columns: {missing}", details=details)

    # Check PK uniqueness
    game_id_col = "GAME_ID" if "GAME_ID" in df.columns else df.columns[0]
    duplicates = df[game_id_col].duplicated().sum()
    if duplicates > 0:
        details["duplicates"] = duplicates
        return GateResult(passed=False, message=f"{duplicates} duplicate GAME_IDs", details=details)

    # Check GAME_DATE coverage (if present)
    if "GAME_DATE" in df.columns:
        null_dates = df["GAME_DATE"].isna().sum()
        coverage = (len(df) - null_dates) / len(df) * 100
        details["date_coverage"] = f"{coverage:.1f}%"
        if coverage < 95:
            return GateResult(
                passed=False, message=f"GAME_DATE coverage {coverage:.1f}% < 95%", details=details
            )

    return GateResult(passed=True, message=f"{len(df)} games indexed", details=details)


def check_raw_gate(df: pd.DataFrame) -> GateResult:
    """Check RAW_GATE: stat sanity checks."""
    issues = []
    details = {"rows_checked": len(df)}

    # FGM <= FGA
    if "FGM" in df.columns and "FGA" in df.columns:
        violations = (df["FGM"] > df["FGA"]).sum()
        if violations > 0:
            issues.append(f"FGM>FGA: {violations}")
            details["fgm_fga_violations"] = violations

    # FG3M <= FG3A
    if "FG3M" in df.columns and "FG3A" in df.columns:
        violations = (df["FG3M"] > df["FG3A"]).sum()
        if violations > 0:
            issues.append(f"FG3M>FG3A: {violations}")
            details["fg3m_fg3a_violations"] = violations

    # FTM <= FTA
    if "FTM" in df.columns and "FTA" in df.columns:
        violations = (df["FTM"] > df["FTA"]).sum()
        if violations > 0:
            issues.append(f"FTM>FTA: {violations}")
            details["ftm_fta_violations"] = violations

    # MIN >= 0
    if "MIN" in df.columns:
        negative = (df["MIN"] < 0).sum()
        if negative > 0:
            issues.append(f"MIN<0: {negative}")
            details["negative_min"] = negative

    # Check players per game (should be ~2 teams)
    if "GAME_ID" in df.columns and "TEAM_KEY" in df.columns:
        teams_per_game = df.groupby("GAME_ID")["TEAM_KEY"].nunique()
        wrong_teams = (teams_per_game != 2).sum()
        if wrong_teams > 0:
            details["games_not_2_teams"] = wrong_teams
            # Warning only - some games may have issues
            if wrong_teams > len(teams_per_game) * 0.1:
                issues.append(f"Games != 2 teams: {wrong_teams}")

    if issues:
        return GateResult(passed=False, message="; ".join(issues), details=details)

    return GateResult(passed=True, message="All stat sanity checks passed", details=details)


def check_canon_gate(df: pd.DataFrame) -> GateResult:
    """Check CANON_GATE: canonical schema compliance."""
    details = {"rows": len(df), "columns": len(df.columns)}

    # Check PK uniqueness
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    pk_present = [c for c in pk_cols if c in df.columns]

    if len(pk_present) < 4:
        missing_pk = [c for c in pk_cols if c not in df.columns]
        return GateResult(
            passed=False, message=f"Missing PK columns: {missing_pk}", details=details
        )

    duplicates = df.duplicated(subset=pk_cols, keep=False).sum()
    if duplicates > 0:
        details["pk_duplicates"] = duplicates
        return GateResult(passed=False, message=f"{duplicates} duplicate PKs", details=details)

    # Check NAME_KEY coverage
    if "NAME_KEY" in df.columns:
        null_names = df["NAME_KEY"].isna().sum()
        coverage = (len(df) - null_names) / len(df) * 100
        details["name_key_coverage"] = f"{coverage:.1f}%"
        if coverage < 90:
            return GateResult(
                passed=False, message=f"NAME_KEY coverage {coverage:.1f}% < 90%", details=details
            )

    # Check required columns present
    missing_req = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_req:
        details["missing_required"] = missing_req
        return GateResult(
            passed=False, message=f"Missing required columns: {missing_req}", details=details
        )

    return GateResult(passed=True, message=f"{len(df)} rows, PK unique", details=details)


def check_gold_gate(league: str, season: str, gold_df: pd.DataFrame | None) -> GateResult:
    """Check GOLD_GATE: data present in gold table."""
    if gold_df is None:
        return GateResult(passed=False, message="Gold table not loaded")

    league_norm = normalize_league(league)

    # Filter to league and season
    league_col = "LEAGUE" if "LEAGUE" in gold_df.columns else None
    season_col = "SEASON" if "SEASON" in gold_df.columns else None

    if not league_col or not season_col:
        return GateResult(passed=False, message="Gold table missing LEAGUE/SEASON columns")

    # Normalize season for comparison
    season_norm = normalize_season(str(season))
    gold_seasons_norm = gold_df[season_col].astype(str).apply(normalize_season)

    mask = (gold_df[league_col].str.upper() == league_norm.upper()) & (
        gold_seasons_norm == season_norm
    )
    subset = gold_df[mask]

    if len(subset) == 0:
        return GateResult(passed=False, message=f"No rows in gold for {league_norm} {season}")

    details = {"rows": len(subset)}

    # Check PK uniqueness in gold subset
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    pk_present = [c for c in pk_cols if c in subset.columns]
    if len(pk_present) >= 3:
        dups = subset.duplicated(subset=pk_present, keep=False).sum()
        if dups > 0:
            details["pk_duplicates"] = dups
            return GateResult(
                passed=False, message=f"{dups} duplicate PKs in gold", details=details
            )

    return GateResult(passed=True, message=f"{len(subset)} rows in gold", details=details)


def check_xwalk_gate(league: str, xwalk_df: pd.DataFrame | None) -> GateResult:
    """Check XWALK_GATE: crosswalk entries exist."""
    if xwalk_df is None:
        return GateResult(passed=False, message="Crosswalk not loaded")

    league_norm = normalize_league(league)

    # Find league column
    league_cols = [c for c in xwalk_df.columns if "league" in c.lower()]
    if not league_cols:
        return GateResult(passed=False, message="No league column in crosswalk")

    # Count entries for this league
    count = 0
    for col in league_cols:
        matches = xwalk_df[col].astype(str).str.upper()
        matches = matches.str.contains(league_norm.upper(), na=False)
        count += matches.sum()

    if count == 0:
        return GateResult(passed=False, message=f"No crosswalk entries for {league_norm}")

    return GateResult(passed=True, message=f"{count} crosswalk links", details={"links": count})


def load_canonical_data(league: str, season: str) -> pd.DataFrame | None:
    """Load canonical data for a league/season."""
    league_norm = normalize_league(league)

    # Try partition path
    partition_path = CANONICAL_PATH / f"league={league_norm}" / f"season={season}"
    if partition_path.exists():
        parquet_files = list(partition_path.glob("*.parquet"))
        if parquet_files:
            return pd.read_parquet(parquet_files[0])

    # Try cache path
    cache_patterns = [
        f"{league_norm}_combined_box_player_game.parquet",
        f"{league}_combined_box_player_game.parquet",
    ]
    for pattern in cache_patterns:
        cache_path = CANONICAL_CACHE_PATH / pattern
        if cache_path.exists():
            df = pd.read_parquet(cache_path)
            # Filter to season if present
            if "SEASON" in df.columns:
                df = df[df["SEASON"].astype(str) == str(season)]
            return df if len(df) > 0 else None

    return None


def validate_league_season(
    league: str, season: str, gold_df: pd.DataFrame | None, xwalk_df: pd.DataFrame | None
) -> ValidationResult:
    """Run all 5 gates for a league/season."""
    league_norm = normalize_league(league)

    # INDEX_GATE
    index_gate = check_index_gate(league_norm, season)

    # Load canonical data for other gates
    canonical_df = load_canonical_data(league_norm, season)

    # RAW_GATE
    if canonical_df is not None:
        raw_gate = check_raw_gate(canonical_df)
    else:
        raw_gate = GateResult(passed=False, message="No canonical data to validate")

    # CANON_GATE
    if canonical_df is not None:
        canon_gate = check_canon_gate(canonical_df)
    else:
        canon_gate = GateResult(passed=False, message="No canonical data found")

    # GOLD_GATE
    gold_gate = check_gold_gate(league_norm, season, gold_df)

    # XWALK_GATE
    xwalk_gate = check_xwalk_gate(league_norm, xwalk_df)

    return ValidationResult(
        league=league_norm,
        season=season,
        index_gate=index_gate,
        raw_gate=raw_gate,
        canon_gate=canon_gate,
        gold_gate=gold_gate,
        xwalk_gate=xwalk_gate,
    )


def get_all_seasons(league: str) -> list:
    """Get all available seasons for a league from game indexes."""
    league_norm = normalize_league(league)
    seasons = set()

    for idx_dir in GAME_INDEX_DIRS:
        if not idx_dir.exists():
            continue
        for f in idx_dir.glob(f"{league_norm}*.csv"):
            # Extract season from filename
            name = f.stem
            parts = name.split("_")
            if len(parts) >= 2:
                season = "_".join(parts[1:])
                seasons.add(season)

    return sorted(seasons)


def main():
    parser = argparse.ArgumentParser(description="5-Gate validation for player game data")
    parser.add_argument("--league", required=True, help="League code (e.g., NBL, ABA)")
    parser.add_argument("--season", help="Season (e.g., 2023-24)")
    parser.add_argument("--all-seasons", action="store_true", help="Validate all available seasons")

    args = parser.parse_args()

    # Load gold table
    gold_df = None
    if GOLD_TABLE_PATH.exists():
        try:
            gold_df = pd.read_parquet(GOLD_TABLE_PATH)
            print(f"Loaded gold table: {len(gold_df):,} rows")
        except Exception as e:
            print(f"Warning: Could not load gold table: {e}")

    # Load crosswalk
    xwalk_df = None
    xwalk_path = UNIFIED_BASE / "cache" / "identity" / "player_xwalk.parquet"
    if xwalk_path.exists():
        try:
            xwalk_df = pd.read_parquet(xwalk_path)
            print(f"Loaded crosswalk: {len(xwalk_df):,} entries")
        except Exception as e:
            print(f"Warning: Could not load crosswalk: {e}")

    # Determine seasons to validate
    if args.all_seasons:
        seasons = get_all_seasons(args.league)
        if not seasons:
            print(f"No seasons found for {args.league}")
            sys.exit(1)
        print(f"Found {len(seasons)} seasons for {args.league}")
    elif args.season:
        seasons = [args.season]
    else:
        print("ERROR: Specify --season or --all-seasons")
        sys.exit(1)

    # Run validation
    results = []
    for season in seasons:
        result = validate_league_season(args.league, season, gold_df, xwalk_df)
        result.print_report()
        results.append(result)

    # Summary
    if len(results) > 1:
        passed = sum(1 for r in results if r.all_passed)
        print(f"\n{'='*60}")
        print(f"SUMMARY: {passed}/{len(results)} seasons passed all gates")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
