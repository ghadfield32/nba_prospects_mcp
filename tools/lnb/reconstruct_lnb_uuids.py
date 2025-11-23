#!/usr/bin/env python3
"""LNB UUID Reconstruction Pipeline (B2 Strategy)

Recovers historical fixture UUIDs by matching public schedule data against
Atrium API candidate pools. Designed to be league-agnostic and repeatable.

Architecture:
1. Load public schedule CSV (date, home_team, away_team, scores)
2. Build Atrium candidate pool (cached per season/league)
3. Match using weighted scoring (date + teams + scores)
4. Write canonical mapping keys + audit report

Usage:
    # Reconstruct single season
    python tools/lnb/reconstruct_lnb_uuids.py \
      --season 2022-2023 \
      --league elite_2 \
      --public-schedule tools/lnb/sources/elite_2_2022-2023.csv

    # Batch reconstruct from manifest
    python tools/lnb/reconstruct_lnb_uuids.py --from-manifest

    # Dry run (no writes)
    python tools/lnb/reconstruct_lnb_uuids.py \
      --season 2023-2024 \
      --league elite_2 \
      --public-schedule tools/lnb/sources/elite_2_2023-2024.csv \
      --dry-run
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# Local imports (handle both direct execution and import from elsewhere)
try:
    from .team_name_normalization import (
        load_team_name_overrides,
        normalize_with_overrides,
    )
except ImportError:
    from team_name_normalization import (
        load_team_name_overrides,
        normalize_with_overrides,
    )

# ==============================================================================
# CONFIGURATION
# ==============================================================================

TOOLS_DIR = Path(__file__).parent
SOURCES_DIR = TOOLS_DIR / "sources"
CACHES_DIR = TOOLS_DIR / "caches"
OUTPUTS_DIR = TOOLS_DIR / "outputs"
MANIFEST_FILE = TOOLS_DIR / "history_manifest.yaml"
MAPPING_FILE = TOOLS_DIR / "fixture_uuids_by_season.json"

# Matching weights (must sum to 1.0)
MATCH_WEIGHTS = {
    "date": 0.5,  # Date proximity
    "teams": 0.4,  # Home/away team name match
    "score": 0.1,  # Final score match (optional)
}

CONFIDENCE_THRESHOLD = 0.8  # Minimum score to accept a match

# ==============================================================================
# PUBLIC SCHEDULE LOADER
# ==============================================================================


def load_public_schedule(csv_path: Path) -> pd.DataFrame:
    """Load public schedule CSV

    Expected columns:
        - date: Game date (YYYY-MM-DD or parseable format)
        - home_team: Home team name
        - away_team: Away team name
        - home_score: Home final score (optional)
        - away_score: Away final score (optional)
        - round: Round/matchday number (optional)

    Args:
        csv_path: Path to public schedule CSV file

    Returns:
        DataFrame with normalized columns

    Raises:
        FileNotFoundError: If CSV doesn't exist
        ValueError: If required columns are missing
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Public schedule not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Validate required columns
    required = ["date", "home_team", "away_team"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Parse dates
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # Add normalized team names
    overrides = load_team_name_overrides()
    df["home_norm"] = df["home_team"].apply(lambda x: normalize_with_overrides(x, overrides))
    df["away_norm"] = df["away_team"].apply(lambda x: normalize_with_overrides(x, overrides))

    print(f"[LOADED] {len(df)} public schedule rows from {csv_path.name}")

    return df


# ==============================================================================
# ATRIUM CANDIDATE POOL BUILDER
# ==============================================================================


def build_candidate_pool(
    season: str,
    league: str,
    cache_path: Path | None = None,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """Build candidate UUID pool from Atrium API

    Strategy:
    1. Check cache first (fast path)
    2. If cache miss or force_rebuild:
       a. Get competition/season IDs from league config
       b. Fetch all fixtures for season/league from Atrium API
       c. Normalize team names for matching
       d. Cache to parquet for reuse

    Args:
        season: Season string (e.g., "2022-2023")
        league: League canonical key (e.g., "elite_2")
        cache_path: Optional custom cache path
        force_rebuild: Ignore cache and rebuild from API

    Returns:
        DataFrame with columns:
            - game_id: Fixture UUID
            - game_date: Date object
            - home_team: Home team name (from API)
            - away_team: Away team name (from API)
            - home_norm: Normalized home team
            - away_norm: Normalized away team
            - home_score: Final home score (if available)
            - away_score: Final away score (if available)

    Raises:
        ValueError: If season/league combination not found in config
        requests.RequestException: If API call fails
    """
    if cache_path is None:
        cache_path = CACHES_DIR / f"atrium_candidates_{season}_{league}.parquet"

    # Check cache
    if not force_rebuild and cache_path.exists():
        df = pd.read_parquet(cache_path)
        print(f"[CACHED] {len(df)} Atrium candidates from {cache_path.name}")
        return df

    print(f"[BUILDING] Atrium candidate pool for {season} / {league}...")

    # Import dependencies (delayed to avoid import at module level)
    import sys
    from pathlib import Path as PathLib

    # Add project root to path if needed
    project_root = PathLib(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.cbb_data.fetchers.lnb_league_config import get_season_metadata
    from tools.lnb.fetch_fixture_metadata_helper import fetch_fixtures_metadata

    # Get competition/season IDs from config
    metadata = get_season_metadata(league, season)
    if not metadata:
        raise ValueError(
            f"No metadata found for {league} / {season}. "
            f"Available leagues: betclic_elite, elite_2, espoirs_elite, espoirs_prob. "
            f"Check src/cbb_data/fetchers/lnb_league_config.py for season coverage."
        )

    competition_id = metadata["competition_id"]
    season_id = metadata["season_id"]
    competition_name = metadata.get("competition_name", "Unknown")

    print("  [API] Fetching fixtures from Atrium...")
    print(f"        League: {league} ({competition_name})")
    print(f"        Competition ID: {competition_id}")
    print(f"        Season ID: {season_id}")
    print("        Endpoint: https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixtures")

    # Fetch fixtures from Atrium API
    try:
        fixtures = fetch_fixtures_metadata(competition_id, season_id)
        print(f"  [ATRIUM] Received {len(fixtures)} fixtures for {season}/{league}")

        # Show sample if fixtures exist
        if fixtures and len(fixtures) > 0:
            print("  [SAMPLE] First 3 fixtures:")
            for i, f in enumerate(fixtures[:3]):
                fid = f.get("fixture_id", "")[:8] + "..."
                date = f.get("game_date", "")
                home = f.get("home_team_name", "")
                away = f.get("away_team_name", "")
                h_score = f.get("home_score", "")
                a_score = f.get("away_score", "")
                status = f.get("status", "")
                print(
                    f"           {i+1}. {date} | {home} vs {away} ({h_score}-{a_score}) [{status}] | {fid}"
                )
    except Exception as e:
        print(f"  [ATRIUM][ERROR] Failed to fetch fixtures for {season}/{league}")
        print(f"                  competition_id={competition_id}")
        print(f"                  season_id={season_id}")
        print(f"                  Error: {e}")
        raise

    if not fixtures:
        print("  [WARN] No fixtures returned from Atrium API")
        df = pd.DataFrame(
            columns=[
                "game_id",
                "game_date",
                "home_team",
                "away_team",
                "home_norm",
                "away_norm",
                "home_score",
                "away_score",
            ]
        )
        return df

    print(f"  [API] Received {len(fixtures)} fixtures from Atrium")

    # Convert to DataFrame
    rows = []
    for fixture in fixtures:
        # Parse game_date from ISO string to date object
        game_date_str = fixture.get("game_date", "")
        try:
            game_date = pd.to_datetime(game_date_str).date()
        except Exception:
            print(f"  [WARN] Invalid date for fixture {fixture.get('fixture_id')}: {game_date_str}")
            continue

        rows.append(
            {
                "game_id": fixture.get("fixture_id", ""),
                "game_date": game_date,
                "home_team": fixture.get("home_team_name", ""),
                "away_team": fixture.get("away_team_name", ""),
                "home_score": fixture.get("home_score", ""),
                "away_score": fixture.get("away_score", ""),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        print("  [WARN] No valid fixtures after parsing")
        return df

    # Normalize team names for matching
    overrides = load_team_name_overrides()
    df["home_norm"] = df["home_team"].apply(lambda x: normalize_with_overrides(x, overrides))
    df["away_norm"] = df["away_team"].apply(lambda x: normalize_with_overrides(x, overrides))

    # Deduplicate by game_id (should be unique, but safety check)
    initial_count = len(df)
    df = df.drop_duplicates(subset=["game_id"], keep="first")
    if len(df) < initial_count:
        print(f"  [INFO] Removed {initial_count - len(df)} duplicate game_ids")

    # Cache to parquet
    CACHES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    print(f"  [SAVED] {len(df)} candidates cached to {cache_path.name}")

    return df


# ==============================================================================
# MATCHING LOGIC
# ==============================================================================


def score_match(public_row: pd.Series, candidate_row: pd.Series) -> float:
    """Score a potential match between public schedule and Atrium candidate

    Weighted scoring based on:
    - Date proximity (exact=1.0, ±1 day=0.7, else=0.0)
    - Team names (both match=1.0, else=0.0)
    - Scores (both match=1.0, else=0.0, or 0.0 if missing)

    Args:
        public_row: Row from public schedule DataFrame
        candidate_row: Row from Atrium candidate DataFrame

    Returns:
        Match confidence score (0.0 to 1.0)
    """
    # Date score
    date_pub = public_row["date"]
    date_cand = candidate_row["game_date"]

    if date_cand == date_pub:
        date_score = 1.0
    elif abs((date_cand - date_pub).days) <= 1:
        date_score = 0.7  # Allow ±1 day for timezone/scheduling differences
    else:
        date_score = 0.0

    # Team name score (must match both home AND away)
    home_match = public_row["home_norm"] == candidate_row["home_norm"]
    away_match = public_row["away_norm"] == candidate_row["away_norm"]
    teams_score = 1.0 if (home_match and away_match) else 0.0

    # Score match (optional)
    score_score = 0.0
    if pd.notna(public_row.get("home_score")) and pd.notna(candidate_row.get("home_score")):
        home_score_match = public_row["home_score"] == candidate_row["home_score"]
        away_score_match = public_row["away_score"] == candidate_row["away_score"]
        score_score = 1.0 if (home_score_match and away_score_match) else 0.0

    # Weighted sum
    total = (
        MATCH_WEIGHTS["date"] * date_score
        + MATCH_WEIGHTS["teams"] * teams_score
        + MATCH_WEIGHTS["score"] * score_score
    )

    return total


def match_public_to_candidates(
    public_df: pd.DataFrame, candidates_df: pd.DataFrame
) -> list[tuple[pd.Series, str | None, float]]:
    """Match public schedule rows to Atrium candidates

    Uses greedy matching with uniqueness constraint (each candidate used once).

    Args:
        public_df: Public schedule DataFrame
        candidates_df: Atrium candidate pool DataFrame

    Returns:
        List of (public_row, matched_game_id, confidence_score) tuples
        game_id is None if no confident match found
    """
    matches = []
    used_game_ids = set()

    print(f"\n[MATCHING] {len(public_df)} public rows against {len(candidates_df)} candidates")

    for idx, pub_row in public_df.iterrows():
        # Narrow candidates by date window (performance optimization)
        date_min = pub_row["date"] - timedelta(days=1)
        date_max = pub_row["date"] + timedelta(days=1)

        window = candidates_df[
            (candidates_df["game_date"] >= date_min) & (candidates_df["game_date"] <= date_max)
        ]

        if window.empty:
            matches.append((pub_row, None, 0.0))
            continue

        # Score all candidates in window
        scored = []
        for _, cand_row in window.iterrows():
            score = score_match(pub_row, cand_row)
            game_id = cand_row["game_id"]

            # Only consider candidates not yet used
            if game_id not in used_game_ids:
                scored.append((score, game_id, cand_row))

        if not scored:
            matches.append((pub_row, None, 0.0))
            continue

        # Take best match
        scored.sort(reverse=True, key=lambda x: x[0])
        best_score, best_id, best_row = scored[0]

        if best_score >= CONFIDENCE_THRESHOLD:
            used_game_ids.add(best_id)
            matches.append((pub_row, best_id, best_score))
        else:
            matches.append((pub_row, None, best_score))

    # Stats
    matched = sum(1 for (_, gid, _) in matches if gid is not None)
    high_conf = sum(1 for (_, gid, score) in matches if gid and score >= 0.9)
    low_conf = sum(1 for (_, gid, score) in matches if gid and CONFIDENCE_THRESHOLD <= score < 0.9)

    print(f"[RESULTS] Matched: {matched}/{len(public_df)} ({matched/len(public_df)*100:.1f}%)")
    print(f"          High confidence (≥0.9): {high_conf}")
    print(f"          Low confidence (0.8-0.9): {low_conf}")
    print(f"          Unmatched: {len(public_df) - matched}")

    return matches


# ==============================================================================
# OUTPUT & REPORTING
# ==============================================================================


def write_reconstruction_results(
    matches: list[tuple[pd.Series, str | None, float]],
    season: str,
    league: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write reconstruction results to mapping file and audit report

    Args:
        matches: Match results from match_public_to_candidates()
        season: Season string
        league: League canonical key
        dry_run: If True, don't write to mapping file

    Returns:
        Audit report dict
    """
    from src.cbb_data.fetchers.lnb_league_normalization import canonical_mapping_key

    # Extract matched UUIDs
    matched_uuids = [gid for (_, gid, score) in matches if gid and score >= CONFIDENCE_THRESHOLD]

    # Get canonical mapping key
    mapping_key = canonical_mapping_key(season, league)

    # Load existing mappings
    if MAPPING_FILE.exists():
        with open(MAPPING_FILE) as f:
            mappings = json.load(f)
    else:
        mappings = {"mappings": {}, "metadata": {}}

    # Update mappings (merge with existing)
    existing = set(mappings.get("mappings", {}).get(mapping_key, []))
    new_uuids = set(matched_uuids)
    combined = sorted(existing | new_uuids)

    if not dry_run:
        if "mappings" not in mappings:
            mappings["mappings"] = {}
        mappings["mappings"][mapping_key] = combined

        # Update metadata
        if "metadata" not in mappings:
            mappings["metadata"] = {}
        mappings["metadata"][f"{mapping_key}_reconstructed_at"] = pd.Timestamp.now().isoformat()
        mappings["metadata"][f"{mapping_key}_reconstruction_method"] = "B2_schedule_matching"

        # Write back to file
        with open(MAPPING_FILE, "w") as f:
            json.dump(mappings, f, indent=2)

        print(f"\n[SAVED] {len(combined)} UUIDs to key: {mapping_key}")
        print(f"        ({len(new_uuids)} new, {len(existing)} existing)")
    else:
        print(f"\n[DRY RUN] Would save {len(combined)} UUIDs to key: {mapping_key}")

    # Build audit report
    unmatched_or_low = [
        {
            "date": str(row["date"]),
            "home": row["home_team"],
            "away": row["away_team"],
            "confidence": score,
            "reason": "no_match" if gid is None else f"low_conf_{score:.2f}",
        }
        for (row, gid, score) in matches
        if gid is None or score < CONFIDENCE_THRESHOLD
    ]

    report = {
        "season": season,
        "league": league,
        "mapping_key": mapping_key,
        "total_public_rows": len(matches),
        "matched": len(matched_uuids),
        "match_rate": len(matched_uuids) / len(matches) if matches else 0.0,
        "existing_uuids": len(existing),
        "new_uuids": len(new_uuids),
        "final_count": len(combined),
        "unmatched_or_lowconf": unmatched_or_low,
    }

    # Save report
    report_path = OUTPUTS_DIR / f"{league}_{season}_reconstruction_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"[REPORT] Saved to: {report_path}")

    return report


# ==============================================================================
# MAIN PIPELINE
# ==============================================================================


def reconstruct_season(
    season: str,
    league: str,
    public_schedule_path: Path,
    force_rebuild_cache: bool = False,
    dry_run: bool = False,
):
    """Run reconstruction pipeline for a single season

    Args:
        season: Season string (e.g., "2022-2023")
        league: League canonical key (e.g., "elite_2")
        public_schedule_path: Path to public schedule CSV
        force_rebuild_cache: Ignore Atrium candidate cache
        dry_run: Don't write to mapping file
    """
    print(f"\n{'='*80}")
    print(f"  RECONSTRUCTING: {season} / {league}")
    print(f"{'='*80}\n")

    # Load public schedule
    public_df = load_public_schedule(public_schedule_path)

    # Build Atrium candidate pool
    candidates_df = build_candidate_pool(
        season=season,
        league=league,
        force_rebuild=force_rebuild_cache,
    )

    if candidates_df.empty:
        print("\n[ERROR] No Atrium candidates available")
        print("        Implement candidate pool building before running reconstruction")
        return None

    # Match
    matches = match_public_to_candidates(public_df, candidates_df)

    # Write results
    report = write_reconstruction_results(
        matches=matches,
        season=season,
        league=league,
        dry_run=dry_run,
    )

    return report


def reconstruct_from_manifest(manifest_path: Path = MANIFEST_FILE, **kwargs):
    """Run reconstruction for all targets in manifest

    Args:
        manifest_path: Path to history manifest YAML
        **kwargs: Additional args passed to reconstruct_season()
    """
    if not manifest_path.exists():
        print(f"[ERROR] Manifest not found: {manifest_path}")
        return

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    targets = [
        t for t in manifest.get("targets", []) if t.get("status") in ["missing_uuids", "partial"]
    ]

    if not targets:
        print("[INFO] No targets needing reconstruction in manifest")
        return

    print(f"\n[MANIFEST] Found {len(targets)} targets needing reconstruction\n")

    for target in targets:
        season = target["season"]
        league = target["league"]

        # Infer CSV path from convention
        csv_path = SOURCES_DIR / f"{league}_{season}.csv"

        if not csv_path.exists():
            print(f"[SKIP] {season}/{league} - no public schedule at {csv_path}")
            continue

        reconstruct_season(
            season=season,
            league=league,
            public_schedule_path=csv_path,
            **kwargs,
        )


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="LNB UUID Reconstruction Pipeline (B2 Strategy)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--season",
        help="Season to reconstruct (e.g., 2022-2023)",
    )
    parser.add_argument(
        "--league",
        help="League canonical key (e.g., elite_2)",
    )
    parser.add_argument(
        "--public-schedule",
        type=Path,
        help="Path to public schedule CSV",
    )
    parser.add_argument(
        "--from-manifest",
        action="store_true",
        help="Reconstruct all targets from history_manifest.yaml",
    )
    parser.add_argument(
        "--force-rebuild-cache",
        action="store_true",
        help="Rebuild Atrium candidate cache (ignore existing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to mapping file (audit only)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.from_manifest:
        reconstruct_from_manifest(
            force_rebuild_cache=args.force_rebuild_cache,
            dry_run=args.dry_run,
        )
    elif args.season and args.league and args.public_schedule:
        reconstruct_season(
            season=args.season,
            league=args.league,
            public_schedule_path=args.public_schedule,
            force_rebuild_cache=args.force_rebuild_cache,
            dry_run=args.dry_run,
        )
    else:
        parser.error("Either --from-manifest OR (--season, --league, --public-schedule) required")


if __name__ == "__main__":
    main()
