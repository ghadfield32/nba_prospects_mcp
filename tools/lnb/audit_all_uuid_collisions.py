#!/usr/bin/env python3
"""Complete UUID Audit - Check all 34 files for UUID collisions

Purpose:
    Systematically audit ALL normalized parquet files to:
    1. Map UUID → (season, teams, score, players)
    2. Detect ALL UUID collisions (same UUID → different games)
    3. Identify pattern of corruption
    4. Generate correction mapping

Debug Approach:
    - Don't assume anything
    - Check every file individually
    - Track all metadata per UUID
    - Show step-by-step what we find
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_ROOT = Path("data")
NORMALIZED_ROOT = DATA_ROOT / "normalized" / "lnb"
TOOLS_ROOT = Path("tools/lnb")

# ==============================================================================
# STEP-BY-STEP AUDIT FUNCTIONS
# ==============================================================================


def extract_game_metadata(file_path: Path, dataset_type: str) -> dict | None:
    """Extract complete metadata from a parquet file

    Args:
        file_path: Path to parquet file
        dataset_type: "player_game" or "team_game"

    Returns:
        Dict with complete game metadata
    """
    try:
        df = pd.read_parquet(file_path)

        if len(df) == 0:
            return None

        # Extract from first row (game-level data)
        first_row = df.iloc[0]

        metadata = {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "folder_season": file_path.parent.name.replace("season=", ""),
            "dataset_type": dataset_type,
            "row_count": len(df),
            "game_id": first_row.get("GAME_ID"),
            "season_in_data": first_row.get("SEASON"),
        }

        if dataset_type == "player_game":
            # Extract player info
            metadata["player_ids"] = sorted(df["PLAYER_ID"].dropna().unique().tolist())
            metadata["player_count"] = len(metadata["player_ids"])
            metadata["player_names"] = sorted(df["PLAYER_NAME"].dropna().unique().tolist())

            # Sample top scorer
            if "PTS" in df.columns and "PLAYER_NAME" in df.columns:
                top_scorer_idx = df["PTS"].idxmax()
                top_scorer = df.loc[top_scorer_idx]
                metadata["top_scorer"] = {
                    "name": top_scorer.get("PLAYER_NAME"),
                    "pts": top_scorer.get("PTS"),
                    "player_id": top_scorer.get("PLAYER_ID"),
                }

        elif dataset_type == "team_game":
            # Extract team info
            if len(df) >= 2:
                team1 = df.iloc[0]
                team2 = df.iloc[1]

                metadata["team1_id"] = team1.get("TEAM_ID")
                metadata["team1_pts"] = team1.get("PTS")
                metadata["team1_fg_pct"] = team1.get("FG_PCT")

                metadata["team2_id"] = team2.get("TEAM_ID")
                metadata["team2_pts"] = team2.get("PTS")
                metadata["team2_fg_pct"] = team2.get("FG_PCT")

                # Create game signature for duplicate detection
                metadata["game_signature"] = (
                    f"{metadata['team1_id']}_{metadata['team2_id']}_{metadata['team1_pts']}_{metadata['team2_pts']}"
                )

        # Create composite key hash for TRUE deduplication
        if dataset_type == "team_game" and len(df) >= 2:
            composite_key = f"{metadata['team1_id']}|{metadata['team2_id']}|{metadata['team1_pts']}|{metadata['team2_pts']}|{metadata['season_in_data']}"
            metadata["game_hash"] = hashlib.sha256(composite_key.encode()).hexdigest()[:16]

        return metadata

    except Exception as e:
        print(f"ERROR extracting metadata from {file_path.name}: {e}")
        return None


def audit_all_files() -> dict:
    """Audit all normalized files for UUID collisions

    Returns:
        Dict mapping UUID → list of game metadata
    """
    print(f"\n{'=' * 80}")
    print("PHASE 1: AUDITING ALL NORMALIZED FILES")
    print(f"{'=' * 80}\n")

    uuid_to_games = defaultdict(list)
    total_files = 0
    errors = []

    # Audit both datasets
    for dataset_type in ["player_game", "team_game"]:
        dataset_root = NORMALIZED_ROOT / dataset_type

        if not dataset_root.exists():
            print(f"❌ Directory not found: {dataset_root}")
            continue

        print(f"\n{'=' * 80}")
        print(f"Auditing: {dataset_type}")
        print(f"{'=' * 80}\n")

        # Find all season directories
        season_dirs = sorted(
            [d for d in dataset_root.iterdir() if d.is_dir() and d.name.startswith("season=")]
        )

        for season_dir in season_dirs:
            season = season_dir.name.replace("season=", "")
            parquet_files = sorted(season_dir.glob("*.parquet"))

            print(f"Season {season}: {len(parquet_files)} files")

            for file_path in parquet_files:
                total_files += 1

                metadata = extract_game_metadata(file_path, dataset_type)

                if metadata:
                    game_id = metadata["game_id"]
                    uuid_to_games[game_id].append(metadata)

                    # Show progress
                    print(
                        f"  ✓ {file_path.name}: UUID={game_id[:16]}..., Season={metadata['season_in_data']}, Rows={metadata['row_count']}"
                    )
                else:
                    errors.append(f"Failed to extract metadata: {file_path}")
                    print(f"  ❌ {file_path.name}: ERROR")

    print(f"\n{'=' * 80}")
    print("AUDIT COMPLETE")
    print(f"{'=' * 80}")
    print(f"Total files audited: {total_files}")
    print(f"Unique UUIDs found: {len(uuid_to_games)}")
    print(f"Errors: {len(errors)}")

    return dict(uuid_to_games)


def detect_collisions(uuid_to_games: dict) -> dict:
    """Detect UUID collisions and analyze patterns

    Args:
        uuid_to_games: Mapping of UUID → list of game metadata

    Returns:
        Dict with collision analysis
    """
    print(f"\n{'=' * 80}")
    print("PHASE 2: DETECTING UUID COLLISIONS")
    print(f"{'=' * 80}\n")

    collisions = []
    unique_uuids = []
    total_unique_games = 0

    for uuid, games in uuid_to_games.items():
        # No collision – appears only once
        if len(games) == 1:
            unique_uuids.append(uuid)
            total_unique_games += 1
            continue

        # Base collision record (now includes richer fields)
        collision = {
            "uuid": uuid,
            "occurrence_count": len(games),
            "games": games,
            "is_true_collision": False,
            "collision_type": None,  # "duplicate" | "team_only" | "player_only" | "mixed"
            "mismatch_reasons": [],  # e.g. ["team_game_signature_mismatch", "player_roster_mismatch"]
            "details": [],  # human-readable notes
        }

        # Group by dataset type
        player_games = [g for g in games if g["dataset_type"] == "player_game"]
        team_games = [g for g in games if g["dataset_type"] == "team_game"]

        # --- Build signatures for comparison ---------------------------------
        # Team game signatures: teams + score
        team_signatures = set()
        for g in team_games:
            sig = g.get("game_signature")
            if sig is not None:
                team_signatures.add(sig)

        # Player roster signatures: sorted player_ids per game
        player_roster_signatures = set()
        for g in player_games:
            player_ids = g.get("player_ids") or []
            # sorted so order doesn’t matter
            roster_sig = tuple(sorted(player_ids))
            player_roster_signatures.add(roster_sig)

        # Seasons in data (from both datasets)
        seasons_in_data = {g.get("season_in_data") for g in games}
        folder_seasons = {g.get("folder_season") for g in games}

        # --- Decide if this is a "true" collision vs duplicate ----------------
        # We treat it as a TRUE collision whenever any of the key signals disagree.
        if len(team_signatures) > 1:
            collision["mismatch_reasons"].append("team_game_signature_mismatch")
            collision["details"].append(f"Different team_game signatures: {team_signatures}")

        if len(player_roster_signatures) > 1:
            collision["mismatch_reasons"].append("player_roster_mismatch")
            collision["details"].append(
                f"Different player rosters across files "
                f"(unique rosters: {len(player_roster_signatures)})"
            )

        if len(seasons_in_data) > 1:
            collision["mismatch_reasons"].append("season_in_data_mismatch")
            collision["details"].append(f"Different SEASON values in data: {seasons_in_data}")

        if len(folder_seasons) > 1:
            collision["details"].append(f"Files live in multiple season folders: {folder_seasons}")

        # True collision if any mismatch reason was detected
        if collision["mismatch_reasons"]:
            collision["is_true_collision"] = True

        # Collision type: where is the inconsistency living?
        if not collision["mismatch_reasons"]:
            collision["collision_type"] = "duplicate"
        else:
            has_team = bool(team_games)
            has_player = bool(player_games)
            if has_team and has_player:
                collision["collision_type"] = "mixed"
            elif has_team:
                collision["collision_type"] = "team_only"
            elif has_player:
                collision["collision_type"] = "player_only"
            else:
                # Shouldn't really happen, but keep it defensive
                collision["collision_type"] = "unknown"

        # --- Logging / debug output ------------------------------------------
        if collision["is_true_collision"]:
            print(f"\n🔴 COLLISION DETECTED: UUID {uuid[:16]}...")
            print(f"   Occurrences: {len(games)}, Type: {collision['collision_type']}")
            print("   Reasons:")
            for reason in collision["mismatch_reasons"]:
                print(f"     - {reason}")

            if team_games:
                print("   Team-game view:")
                for idx, game in enumerate(team_games, 1):
                    print(f"     [{idx}] Folder: {game['folder_season']}")
                    print(
                        f"         Teams: {game.get('team1_id', 'N/A')} vs {game.get('team2_id', 'N/A')}"
                    )
                    print(
                        f"         Score: {game.get('team1_pts')} - {game.get('team2_pts')}, "
                        f"Season: {game.get('season_in_data')}, "
                        f"Game hash: {game.get('game_hash')}"
                    )

            if player_games:
                print("   Player-game view:")
                for idx, game in enumerate(player_games, 1):
                    print(f"     [{idx}] Folder: {game['folder_season']}")
                    print(
                        f"         Season: {game.get('season_in_data')}, "
                        f"Players: {game.get('player_count', 'N/A')}"
                    )
        else:
            # No mismatches found → same game, multiple copies
            print(f"\n🟡 TRUE DUPLICATE: UUID {uuid[:16]}...")
            print(f"   Same underlying game appears {len(games)} times.")
            if team_games:
                # Reuse original summary style based on team stats
                for idx, game in enumerate(team_games, 1):
                    print(
                        f"   [{idx}] {game['folder_season']}: "
                        f"{game.get('team1_pts')} - {game.get('team2_pts')} "
                        f"(Season in data: {game.get('season_in_data')})"
                    )
            else:
                # Fall back to player-game summary if we only have player data
                for idx, game in enumerate(player_games, 1):
                    print(
                        f"   [{idx}] {game['folder_season']}: "
                        f"{game.get('player_count', 'N/A')} players, "
                        f"Season in data: {game.get('season_in_data')}"
                    )

        # Estimate how many *unique* games this UUID represents
        if collision["is_true_collision"]:
            estimates = []
            if team_signatures:
                estimates.append(len(team_signatures))
            if player_roster_signatures:
                estimates.append(len(player_roster_signatures))
            if not estimates:
                estimates.append(len(seasons_in_data))

            total_unique_games += max(estimates) if estimates else 2
        else:
            total_unique_games += 1

        collisions.append(collision)

    print(f"\n{'=' * 80}")
    print("COLLISION DETECTION SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total UUIDs: {len(uuid_to_games)}")
    print(f"UUIDs with collisions: {len(collisions)}")
    print(f"UUIDs appearing only once: {len(unique_uuids)}")
    print(f"Estimated unique games: {total_unique_games}")

    true_collisions = [c for c in collisions if c["is_true_collision"]]
    true_duplicates = [c for c in collisions if not c["is_true_collision"]]

    print("\nBreakdown:")
    print(f"  True collisions (same UUID → different games): {len(true_collisions)}")
    print(f"  True duplicates (same game in multiple folders): {len(true_duplicates)}")

    return {
        "total_uuids": len(uuid_to_games),
        "collisions": collisions,
        "unique_uuids": unique_uuids,
        "true_collisions": true_collisions,
        "true_duplicates": true_duplicates,
        "estimated_unique_games": total_unique_games,
    }


def generate_correction_mapping(collision_analysis: dict, uuid_to_games: dict) -> dict:
    """Generate UUID correction mapping for corrupted UUIDs

    Args:
        collision_analysis: Collision detection results
        uuid_to_games: Complete UUID mapping

    Returns:
        Correction mapping
    """
    print(f"\n{'=' * 80}")
    print("PHASE 3: GENERATING CORRECTION MAPPING")
    print(f"{'=' * 80}\n")

    corrections = []

    for collision in collision_analysis["true_collisions"]:
        uuid = collision["uuid"]
        games = collision["games"]

        # Get team_game entries (most reliable)
        team_games = [g for g in games if g["dataset_type"] == "team_game"]

        for game in team_games:
            # Generate new UUID based on game hash
            game_hash = game.get("game_hash")

            if game_hash:
                new_uuid = f"LNB_{game['season_in_data'].replace('-', '')}_{game_hash}"

                correction = {
                    "old_uuid": uuid,
                    "new_uuid": new_uuid,
                    "file_path": game["file_path"],
                    "folder_season": game["folder_season"],
                    "season_in_data": game["season_in_data"],
                    "team1_id": game.get("team1_id"),
                    "team2_id": game.get("team2_id"),
                    "score": f"{game.get('team1_pts')}-{game.get('team2_pts')}",
                    "game_hash": game_hash,
                    "correction_needed": True,
                }

                corrections.append(correction)

                print("Correction needed:")
                print(f"  File: {game['file_name']}")
                print(f"  Old UUID: {uuid}")
                print(f"  New UUID: {new_uuid}")
                print(f"  Season: {game['season_in_data']}")
                print()

    print(f"Total corrections needed: {len(corrections)}")

    return {
        "corrections": corrections,
        "total_corrections": len(corrections),
    }


def main():
    """Main audit workflow"""

    print(f"{'#' * 80}")
    print("# COMPLETE UUID AUDIT - ALL 34 FILES")
    print(f"# Started: {datetime.now().isoformat()}")
    print(f"{'#' * 80}\n")

    # Phase 1: Audit all files
    uuid_to_games = audit_all_files()

    # Phase 2: Detect collisions
    collision_analysis = detect_collisions(uuid_to_games)

    # Phase 3: Generate corrections
    correction_mapping = generate_correction_mapping(collision_analysis, uuid_to_games)

    # Compile full report
    report = {
        "generated_at": datetime.now().isoformat(),
        "audit_summary": {
            "total_files_audited": sum(len(games) for games in uuid_to_games.values()),
            "total_unique_uuids": len(uuid_to_games),
            "estimated_unique_games": collision_analysis["estimated_unique_games"],
        },
        "uuid_to_games_mapping": {
            uuid: [
                {
                    "file_path": g["file_path"],
                    "folder_season": g["folder_season"],
                    "season_in_data": g["season_in_data"],
                    "dataset_type": g["dataset_type"],
                    "row_count": g["row_count"],
                    "game_signature": g.get("game_signature"),
                    "game_hash": g.get("game_hash"),
                }
                for g in games
            ]
            for uuid, games in uuid_to_games.items()
        },
        "collision_analysis": {
            "total_collisions": len(collision_analysis["collisions"]),
            "true_collisions": len(collision_analysis["true_collisions"]),
            "true_duplicates": len(collision_analysis["true_duplicates"]),
            "collisions": collision_analysis["collisions"],
        },
        "correction_mapping": correction_mapping,
    }

    # Save report
    output_file = TOOLS_ROOT / "complete_uuid_audit.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'=' * 80}")
    print("AUDIT COMPLETE")
    print(f"{'=' * 80}")
    print(f"Report saved: {output_file}\n")

    # Summary
    print(f"{'#' * 80}")
    print("# FINAL SUMMARY")
    print(f"{'#' * 80}\n")

    print(f"Files Audited: {report['audit_summary']['total_files_audited']}")
    print(f"Unique UUIDs: {report['audit_summary']['total_unique_uuids']}")
    print(f"Estimated Unique Games: {report['audit_summary']['estimated_unique_games']}")
    print()

    print("UUID Collisions:")
    print(
        f"  True collisions (same UUID → different games): {report['collision_analysis']['true_collisions']}"
    )
    print(
        f"  True duplicates (same game in multiple folders): {report['collision_analysis']['true_duplicates']}"
    )
    print()

    print(f"Corrections Needed: {correction_mapping['total_corrections']} files")
    print()


if __name__ == "__main__":
    main()
