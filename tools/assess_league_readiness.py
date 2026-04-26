#!/usr/bin/env python3
"""League Readiness Assessment Tool

Assesses each basketball league for production readiness based on:
1. SOURCE_PLAYER_ID coverage ≥95%
2. PLAYER_NAME quality (not jersey numbers/NULL)
3. Bio data availability (birth_year OR height ≥60%)
4. Current season data available
5. No critical fetcher errors

Usage:
    python tools/assess_league_readiness.py
    python tools/assess_league_readiness.py --leagues NCAA_MBB GLEAGUE
    python tools/assess_league_readiness.py --season 2023-24
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_canonical_data(league: str, season: str = "2024-25") -> pd.DataFrame:
    """Load canonical data for a league and season.

    Handles Hive-style partitioning: box_player_game/league={LEAGUE}/season={SEASON}/data.parquet
    """

    # League code normalization (handle underscore variants)
    league_code_map = {
        "GLEAGUE": "G_LEAGUE",
        "G_LEAGUE": "G_LEAGUE",
        "LNBPROA": "LNB_PROA",
        "LNB_PROA": "LNB_PROA",
    }
    league_normalized = league_code_map.get(league, league)

    # Convert season format from "2024-25" to various formats
    if "-" in season:
        season_parts = season.split("-")
        season_year = int(season_parts[0]) + 1  # Year after (2024-25 -> 2025)

        # Try multiple season formats
        season_formats = [
            str(season_year),  # "2025"
            season,  # "2024-25"
            f"{season_parts[0]}-{season_year}",  # "2024-2025"
            f"{season_year}-{int(season_parts[1])+1 if len(season_parts[1])==2 else int(season_parts[1])+1}",  # "2025-26"
        ]
    else:
        season_year = int(season)
        season_formats = [season]

    # Try Hive-style partitioned paths
    base_paths = [
        Path(__file__).parent.parent / "data",
        Path("data"),
        Path("../data"),
    ]

    for base_path in base_paths:
        league_dir = base_path / "canonical" / "box_player_game" / f"league={league_normalized}"

        if not league_dir.exists():
            continue

        # Try each season format
        for season_fmt in season_formats:
            partitioned_path = league_dir / f"season={season_fmt}" / "data.parquet"

            if partitioned_path.exists():
                try:
                    df = pd.read_parquet(partitioned_path)

                    # Add LEAGUE and SEASON columns if missing (due to partitioning)
                    if "LEAGUE" not in df.columns or df["LEAGUE"].isna().all():
                        df["LEAGUE"] = league_normalized
                    if "SEASON" not in df.columns or df["SEASON"].isna().all():
                        df["SEASON"] = season_year

                    return df
                except Exception as e:
                    print(f"  Error loading {partitioned_path}: {e}")
                    continue

        # Try flat structure (fallback)
        flat_path = base_path / "canonical" / league_normalized / "player_game.parquet"
        if flat_path.exists():
            try:
                df = pd.read_parquet(flat_path)
                # Filter to specific season if SEASON column exists
                if "SEASON" in df.columns or "SOURCE_SEASON" in df.columns:
                    season_col = "SOURCE_SEASON" if "SOURCE_SEASON" in df.columns else "SEASON"
                    df = df[df[season_col] == season_year]
                return df
            except Exception as e:
                print(f"  Error loading {flat_path}: {e}")
                continue

    raise FileNotFoundError(
        f"Could not find canonical data for {league_normalized} season {season}"
    )


def assess_league(league: str, season: str = "2024-25") -> dict:
    """
    Assess a single league for production readiness.

    Returns dict with:
    - league: str
    - tier: int (1=production-ready, 2=needs fixes, 3=defer)
    - source_id_coverage_pct: float
    - name_quality_pct: float
    - bio_coverage_pct: float
    - current_season_games: int
    - issues: list[str]
    """

    try:
        # Load data
        canonical_df = load_canonical_data(league, season=season)

        # Check 1: SOURCE_PLAYER_ID coverage
        id_col = "SOURCE_PLAYER_ID" if "SOURCE_PLAYER_ID" in canonical_df.columns else "PLAYER_ID"
        if id_col in canonical_df.columns:
            id_coverage = canonical_df[id_col].notna().mean() * 100
        else:
            id_coverage = 0.0

        # Check 2: Player name quality
        name_col = "PLAYER_NAME_RAW" if "PLAYER_NAME_RAW" in canonical_df.columns else "PLAYER_NAME"
        if name_col in canonical_df.columns:
            jersey_pattern = re.compile(r"^\d{1,2}$")
            bad_names = canonical_df[name_col].astype(str).str.match(jersey_pattern, na=False).sum()
            name_quality = (
                ((len(canonical_df) - bad_names) / len(canonical_df) * 100)
                if len(canonical_df) > 0
                else 0
            )
        else:
            bad_names = 0
            name_quality = 100.0

        # Check 3: Bio data availability
        birth_data = 0.0
        height_data = 0.0

        if "BIRTH_YEAR" in canonical_df.columns:
            birth_data = canonical_df["BIRTH_YEAR"].notna().mean() * 100
        elif "birth_year" in canonical_df.columns:
            birth_data = canonical_df["birth_year"].notna().mean() * 100

        if "HEIGHT_CM" in canonical_df.columns:
            height_data = canonical_df["HEIGHT_CM"].notna().mean() * 100
        elif "height_cm" in canonical_df.columns:
            height_data = canonical_df["height_cm"].notna().mean() * 100

        bio_coverage = max(birth_data, height_data)

        # Check 4: Current season games
        current_games = len(canonical_df)

        # Determine tier
        if id_coverage >= 95 and name_quality >= 95 and current_games >= 100:
            tier = 1  # Production-ready
        elif id_coverage >= 80 and name_quality >= 80:
            tier = 2  # Needs fixes but recoverable
        else:
            tier = 3  # Defer until enrichment

        # Build assessment
        assessment = {
            "league": league,
            "tier": tier,
            "source_id_coverage_pct": round(id_coverage, 1),
            "name_quality_pct": round(name_quality, 1),
            "bio_coverage_pct": round(bio_coverage, 1),
            "birth_year_pct": round(birth_data, 1),
            "height_cm_pct": round(height_data, 1),
            "current_season_games": current_games,
            "issues": [],
        }

        # Flag specific issues
        if id_coverage < 95:
            assessment["issues"].append(f"LOW_ID_COVERAGE ({id_coverage:.1f}%)")
        if name_quality < 95:
            assessment["issues"].append(f"BAD_NAMES ({bad_names} jersey numbers)")
        if bio_coverage < 60:
            assessment["issues"].append(f"LOW_BIO ({bio_coverage:.1f}%)")
        if current_games < 100:
            assessment["issues"].append(f"LOW_GAMES ({current_games} games)")

        return assessment

    except FileNotFoundError as e:
        return {
            "league": league,
            "tier": 3,
            "source_id_coverage_pct": 0.0,
            "name_quality_pct": 0.0,
            "bio_coverage_pct": 0.0,
            "birth_year_pct": 0.0,
            "height_cm_pct": 0.0,
            "current_season_games": 0,
            "issues": [f"FILE_NOT_FOUND: {str(e)}"],
        }
    except Exception as e:
        return {
            "league": league,
            "tier": 3,
            "source_id_coverage_pct": 0.0,
            "name_quality_pct": 0.0,
            "bio_coverage_pct": 0.0,
            "birth_year_pct": 0.0,
            "height_cm_pct": 0.0,
            "current_season_games": 0,
            "issues": [f"FETCH_ERROR: {str(e)}"],
        }


def assess_league_readiness(leagues: list[str] = None, season: str = "2024-25") -> pd.DataFrame:
    """
    Assess multiple leagues for production readiness.

    Args:
        leagues: List of league codes to assess. If None, assess all known leagues.
        season: Season to assess (default: 2024-25)

    Returns:
        DataFrame with assessment results
    """

    if leagues is None:
        leagues = [
            "NCAA_MBB",
            "GLEAGUE",
            "EUROLEAGUE",
            "ACB",
            "LNB_PROA",
            "NBL",
            "OTE",
            "ABA",
            "CEBL",
        ]

    print("\n" + "=" * 80)
    print(f"LEAGUE READINESS ASSESSMENT - Season: {season}")
    print("=" * 80)

    assessments = []

    for league in leagues:
        print(f"\nAssessing {league}...")
        assessment = assess_league(league, season=season)
        assessments.append(assessment)

    # Convert to DataFrame
    df = pd.DataFrame(assessments)

    # Sort by tier, then by current_season_games
    df = df.sort_values(["tier", "current_season_games"], ascending=[True, False])

    # Export report
    reports_dir = Path("data/_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    output_file = reports_dir / f"league_readiness_assessment_{season.replace('-', '_')}.csv"
    df.to_csv(output_file, index=False)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for _, row in df.iterrows():
        tier_icon = "✓" if row["tier"] == 1 else "⚠" if row["tier"] == 2 else "✗"

        # Format display string
        display = (
            f"{tier_icon} Tier {row['tier']}: {row['league']:<15} "
            f"(ID: {row['source_id_coverage_pct']:>5.1f}%, "
            f"Names: {row['name_quality_pct']:>5.1f}%, "
            f"Bio: {row['bio_coverage_pct']:>5.1f}%, "
            f"Games: {row['current_season_games']:>4})"
        )
        print(display)

        if row.get("issues") and len(row["issues"]) > 0:
            for issue in row["issues"]:
                print(f"    - {issue}")

    # Tier summary
    print("\n" + "-" * 80)
    tier_counts = df["tier"].value_counts().sort_index()
    print(f"Tier 1 (Production-Ready): {tier_counts.get(1, 0)} leagues")
    print(f"Tier 2 (Needs Fixes):      {tier_counts.get(2, 0)} leagues")
    print(f"Tier 3 (Defer):            {tier_counts.get(3, 0)} leagues")

    print(f"\nReport saved to: {output_file}")

    return df


def main():
    """Command-line interface."""

    parser = argparse.ArgumentParser(
        description="Assess basketball leagues for production readiness"
    )
    parser.add_argument(
        "--leagues", nargs="+", help="Specific leagues to assess (default: all)", default=None
    )
    parser.add_argument("--season", default="2024-25", help="Season to assess (default: 2024-25)")

    args = parser.parse_args()

    # Run assessment
    assess_league_readiness(leagues=args.leagues, season=args.season)

    return 0


if __name__ == "__main__":
    sys.exit(main())
