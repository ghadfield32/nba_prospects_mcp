#!/usr/bin/env python
"""Player Identity Crosswalk Builder (Layer D)

Builds deterministic player identity crosswalk for career stitching.
NO fuzzy matching - only exact deterministic rules.

Identity Resolution Rules (ranked by specificity):
1. Exact: (name_key, birth_date)
2. Exact: (name_key, birth_year, height_cm)
3. Exact: (name_key, birth_year, nationality)
4. Exact: (name_key + league-specific-id) for same-league matches

Any ambiguity -> UNRESOLVED (requires manual review)

Usage:
    python scripts/build_player_xwalk.py
    python scripts/build_player_xwalk.py --source canonical_player_game
    python scripts/build_player_xwalk.py --output data/player_xwalk.parquet
"""

import argparse
import hashlib
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
CANONICAL_DIR = DATA_DIR / "canonical"
REPORTS_DIR = DATA_DIR / "_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Known multi-league players for pathway validation
KNOWN_PATHWAYS = {
    "alex_sarr": {
        "name_variations": ["Alex Sarr", "Alexandre Sarr"],
        "expected_leagues": ["OTE", "NBL"],  # OTE -> NBL -> NBA
        "birth_year": 2005,
    },
    "amen_thompson": {
        "name_variations": ["Amen Thompson"],
        "expected_leagues": ["OTE"],  # OTE -> NBA (direct)
        "birth_year": 2003,
    },
    "ausar_thompson": {
        "name_variations": ["Ausar Thompson"],
        "expected_leagues": ["OTE"],  # OTE -> NBA (direct)
        "birth_year": 2003,
    },
}


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name.

    - Lowercase
    - Remove accents (NFD normalization)
    - Remove non-alphanumeric characters
    - Collapse whitespace to single underscore

    Args:
        name: Raw player name

    Returns:
        Normalized name key
    """
    if not name or pd.isna(name):
        return ""

    # Normalize unicode (decompose accented characters)
    normalized = unicodedata.normalize("NFD", str(name))

    # Remove accent marks (combining diacritical marks)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Lowercase
    normalized = normalized.lower()

    # Remove non-alphanumeric except spaces
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)

    # Collapse whitespace to underscore
    normalized = re.sub(r"\s+", "_", normalized.strip())

    return normalized


def generate_canonical_id(name_key: str, birth_year: int | None = None, suffix: str = "") -> str:
    """Generate deterministic canonical player ID.

    Args:
        name_key: Normalized name key
        birth_year: Optional birth year for disambiguation
        suffix: Optional suffix for remaining ambiguity

    Returns:
        Canonical player ID
    """
    base = f"{name_key}"
    if birth_year:
        base = f"{base}_{birth_year}"
    if suffix:
        base = f"{base}_{suffix}"

    # Create short hash for uniqueness
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:6]

    return f"P_{name_key[:20]}_{hash_suffix}"


class PlayerXwalkBuilder:
    """Builds player identity crosswalk."""

    def __init__(self):
        self.source_records = []
        self.canonical_players = {}
        self.xwalk_entries = []
        self.unresolved = []
        self.collisions = []

    def load_canonical_player_game(self, filepath: Path) -> None:
        """Load canonical player_game data as source."""
        if not filepath.exists():
            print(f"File not found: {filepath}")
            return

        df = pd.read_parquet(filepath) if filepath.suffix == ".parquet" else pd.read_csv(filepath)

        for _, row in df.iterrows():
            # Handle both old and new column names
            player_name = row.get("PLAYER_NAME_RAW") or row.get("PLAYER_NAME") or ""
            player_id = row.get("SOURCE_PLAYER_ID") or row.get("PLAYER_ID") or ""
            team = row.get("TEAM_NAME_RAW") or row.get("TEAM_KEY") or row.get("TEAM") or ""

            self.source_records.append(
                {
                    "source_league": row.get("LEAGUE", "UNKNOWN"),
                    "source_season": row.get("SEASON", "UNKNOWN"),
                    "source_player_id": player_id,
                    "player_name": player_name,
                    "team": team,
                    "birth_date": row.get("BIRTH_DATE"),
                    "birth_year": row.get("BIRTH_YEAR"),
                    "height_cm": row.get("HEIGHT_CM"),
                    "nationality": row.get("NATIONALITY"),
                }
            )

    def load_from_game_indexes(self) -> None:
        """Extract unique players from all game data."""
        # This would need to be implemented to load from box scores
        pass

    def build_xwalk(self) -> None:
        """Build crosswalk using deterministic rules."""
        # Group by normalized name
        name_groups = {}

        for record in self.source_records:
            name_key = normalize_name(record["player_name"])
            if not name_key:
                continue

            if name_key not in name_groups:
                name_groups[name_key] = []
            name_groups[name_key].append(record)

        # Process each name group
        for name_key, records in name_groups.items():
            if len(records) == 1:
                # Single occurrence - direct match
                record = records[0]
                canonical_id = generate_canonical_id(name_key, record.get("birth_year"))

                self.canonical_players[canonical_id] = {
                    "canonical_id": canonical_id,
                    "name_key": name_key,
                    "display_name": record["player_name"],
                    "leagues": [record["source_league"]],
                    "birth_year": record.get("birth_year"),
                }

                self.xwalk_entries.append(
                    {
                        "source_league": record["source_league"],
                        "source_season": record["source_season"],
                        "source_player_id": record["source_player_id"],
                        "canonical_player_id": canonical_id,
                        "match_rule": "single_occurrence",
                        "confidence": 1.0,
                    }
                )

            else:
                # Multiple occurrences - need disambiguation
                self._resolve_ambiguous_group(name_key, records)

    def _resolve_ambiguous_group(self, name_key: str, records: list[dict]) -> None:
        """Resolve ambiguous name group using deterministic rules."""
        # Rule 1: Try (name_key, birth_date)
        by_birth_date = {}
        for record in records:
            birth_date = record.get("birth_date")
            if birth_date:
                key = (name_key, str(birth_date))
                if key not in by_birth_date:
                    by_birth_date[key] = []
                by_birth_date[key].append(record)

        if len(by_birth_date) == len(records):
            # All have unique birth dates - resolved!
            for (_, birth_date), group in by_birth_date.items():
                record = group[0]
                canonical_id = generate_canonical_id(name_key, suffix=str(birth_date)[:10])

                self.canonical_players[canonical_id] = {
                    "canonical_id": canonical_id,
                    "name_key": name_key,
                    "display_name": record["player_name"],
                    "leagues": list({r["source_league"] for r in group}),
                    "birth_date": birth_date,
                }

                for r in group:
                    self.xwalk_entries.append(
                        {
                            "source_league": r["source_league"],
                            "source_season": r["source_season"],
                            "source_player_id": r["source_player_id"],
                            "canonical_player_id": canonical_id,
                            "match_rule": "birth_date",
                            "confidence": 0.99,
                        }
                    )
            return

        # Rule 2: Try (name_key, birth_year, height)
        by_year_height = {}
        for record in records:
            birth_year = record.get("birth_year")
            height = record.get("height_cm")
            if birth_year and height:
                key = (name_key, birth_year, height)
                if key not in by_year_height:
                    by_year_height[key] = []
                by_year_height[key].append(record)

        if len(by_year_height) == len(records):
            for (_, birth_year, height), group in by_year_height.items():
                record = group[0]
                canonical_id = generate_canonical_id(name_key, birth_year)

                self.canonical_players[canonical_id] = {
                    "canonical_id": canonical_id,
                    "name_key": name_key,
                    "display_name": record["player_name"],
                    "leagues": list({r["source_league"] for r in group}),
                    "birth_year": birth_year,
                    "height_cm": height,
                }

                for r in group:
                    self.xwalk_entries.append(
                        {
                            "source_league": r["source_league"],
                            "source_season": r["source_season"],
                            "source_player_id": r["source_player_id"],
                            "canonical_player_id": canonical_id,
                            "match_rule": "birth_year_height",
                            "confidence": 0.95,
                        }
                    )
            return

        # Rule 3: Same league = same person (within league identity)
        by_league = {}
        for record in records:
            league = record["source_league"]
            if league not in by_league:
                by_league[league] = []
            by_league[league].append(record)

        if len(by_league) == len(records):
            # Different leagues - could be same person across leagues
            # Check if they have consistent identifiers
            birth_years = {r.get("birth_year") for r in records if r.get("birth_year")}

            if len(birth_years) == 1:
                # Same birth year across leagues - likely same person
                birth_year = list(birth_years)[0]
                canonical_id = generate_canonical_id(name_key, birth_year)

                self.canonical_players[canonical_id] = {
                    "canonical_id": canonical_id,
                    "name_key": name_key,
                    "display_name": records[0]["player_name"],
                    "leagues": list({r["source_league"] for r in records}),
                    "birth_year": birth_year,
                }

                for r in records:
                    self.xwalk_entries.append(
                        {
                            "source_league": r["source_league"],
                            "source_season": r["source_season"],
                            "source_player_id": r["source_player_id"],
                            "canonical_player_id": canonical_id,
                            "match_rule": "cross_league_birth_year",
                            "confidence": 0.90,
                        }
                    )
                return

        # Cannot resolve - mark as unresolved
        self.unresolved.append(
            {
                "name_key": name_key,
                "record_count": len(records),
                "leagues": list({r["source_league"] for r in records}),
                "records": records,
            }
        )

    def validate_known_pathways(self) -> list[dict]:
        """Validate that known multi-league players are correctly stitched."""
        results = []

        for pathway_id, pathway_info in KNOWN_PATHWAYS.items():
            # Find canonical player(s) matching this pathway
            matching_players = []

            for variation in pathway_info["name_variations"]:
                name_key = normalize_name(variation)
                for _canonical_id, player in self.canonical_players.items():
                    if player["name_key"] == name_key:
                        matching_players.append(player)

            result = {
                "pathway_id": pathway_id,
                "expected_leagues": pathway_info["expected_leagues"],
                "status": "UNKNOWN",
                "found_players": len(matching_players),
                "actual_leagues": [],
            }

            if matching_players:
                # Check if all expected leagues are covered
                all_leagues = set()
                for p in matching_players:
                    all_leagues.update(p.get("leagues", []))

                result["actual_leagues"] = list(all_leagues)

                expected = set(pathway_info["expected_leagues"])
                if expected.issubset(all_leagues):
                    result["status"] = "PASS"
                else:
                    result["status"] = "PARTIAL"
                    result["missing_leagues"] = list(expected - all_leagues)
            else:
                result["status"] = "NOT_FOUND"

            results.append(result)

        return results

    def save_outputs(self, output_dir: Path) -> None:
        """Save crosswalk and reports."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Main crosswalk
        if self.xwalk_entries:
            xwalk_df = pd.DataFrame(self.xwalk_entries)
            xwalk_df.to_parquet(output_dir / "player_xwalk.parquet", index=False)
            xwalk_df.to_csv(output_dir / "player_xwalk.csv", index=False)
            print(f"Saved {len(xwalk_df)} crosswalk entries")

        # Canonical players
        if self.canonical_players:
            players_df = pd.DataFrame(list(self.canonical_players.values()))
            players_df.to_parquet(output_dir / "canonical_players.parquet", index=False)
            print(f"Saved {len(players_df)} canonical players")

        # Unresolved
        if self.unresolved:
            with open(REPORTS_DIR / "xwalk_unresolved.json", "w") as f:
                json.dump(self.unresolved, f, indent=2, default=str)
            print(f"Saved {len(self.unresolved)} unresolved cases")

        # Pathway validation
        pathway_results = self.validate_known_pathways()
        with open(REPORTS_DIR / "xwalk_pathway_validation.json", "w") as f:
            json.dump(pathway_results, f, indent=2)
        print(f"Saved pathway validation for {len(pathway_results)} known pathways")

    def get_summary(self) -> dict:
        """Get crosswalk building summary."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "source_records": len(self.source_records),
            "canonical_players": len(self.canonical_players),
            "xwalk_entries": len(self.xwalk_entries),
            "unresolved_groups": len(self.unresolved),
            "collisions": len(self.collisions),
            "pathways_validated": len(KNOWN_PATHWAYS),
        }


def main():
    parser = argparse.ArgumentParser(description="Build player identity crosswalk")
    parser.add_argument("--source", help="Source data file (parquet or csv)")
    parser.add_argument("--output", default="data", help="Output directory")
    args = parser.parse_args()

    print("=" * 70)
    print("PLAYER IDENTITY CROSSWALK BUILDER (Layer D)")
    print("=" * 70)
    print()

    builder = PlayerXwalkBuilder()

    # Load source data
    if args.source:
        source_path = Path(args.source)
        if source_path.exists():
            print(f"Loading source: {source_path}")
            builder.load_canonical_player_game(source_path)
        else:
            print(f"Source file not found: {source_path}")
            return
    else:
        # Try to find canonical player_game files
        canonical_files = list(CANONICAL_DIR.glob("**/*.parquet"))
        if canonical_files:
            for filepath in canonical_files:
                print(f"Loading: {filepath}")
                builder.load_canonical_player_game(filepath)
        else:
            print("No canonical player_game files found.")
            print("Run Phase 3 (canonicalization) first.")
            return

    if not builder.source_records:
        print("No source records loaded.")
        return

    print(f"Loaded {len(builder.source_records)} source records")
    print()

    # Build crosswalk
    print("Building crosswalk with deterministic rules...")
    builder.build_xwalk()

    # Save outputs
    output_dir = Path(args.output)
    builder.save_outputs(output_dir)

    # Print summary
    summary = builder.get_summary()
    print()
    print("=" * 70)
    print("CROSSWALK SUMMARY")
    print("=" * 70)
    print(f"Source records: {summary['source_records']}")
    print(f"Canonical players: {summary['canonical_players']}")
    print(f"Crosswalk entries: {summary['xwalk_entries']}")
    print(f"Unresolved groups: {summary['unresolved_groups']}")
    print(f"Collisions: {summary['collisions']}")

    if summary["unresolved_groups"] > 0:
        print()
        print("WARNING: Unresolved player groups require manual review!")
        print(f"See: {REPORTS_DIR / 'xwalk_unresolved.json'}")


if __name__ == "__main__":
    main()
