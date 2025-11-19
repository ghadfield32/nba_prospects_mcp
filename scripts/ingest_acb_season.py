#!/usr/bin/env python
"""ACB Season Data Ingestion Script

Fetches all ACB (Spanish Liga Endesa) data for a given season:
- Schedule/game index
- Box scores (player game stats)
- Play-by-play (requires BAwiR/rpy2)
- Shot charts (requires BAwiR/rpy2)
- Season aggregates (player/team)

Usage:
    python scripts/ingest_acb_season.py --season 2024
    python scripts/ingest_acb_season.py --season 2024 --skip-pbp
    python scripts/ingest_acb_season.py --season 2024 --output data/raw/acb

Output:
    - data/raw/acb/schedule_{season}.parquet
    - data/raw/acb/player_game_{season}.parquet
    - data/raw/acb/team_game_{season}.parquet
    - data/raw/acb/player_season_{season}.parquet
    - data/raw/acb/team_season_{season}.parquet
    - data/raw/acb/pbp_{season}.parquet (if rpy2 available)
    - data/raw/acb/shots_{season}.parquet (if rpy2 available)
"""

import argparse
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd


def ingest_acb_season(
    season: str,
    output_dir: Path,
    skip_pbp: bool = False,
    skip_shots: bool = False,
) -> dict:
    """Ingest all ACB data for a season.

    Args:
        season: Season string (e.g., "2024")
        output_dir: Output directory for parquet files
        skip_pbp: Skip play-by-play ingestion
        skip_shots: Skip shot chart ingestion

    Returns:
        Ingestion summary with counts and errors
    """
    from cbb_data.fetchers import acb

    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "season": season,
        "schedule": 0,
        "player_game": 0,
        "team_game": 0,
        "player_season": 0,
        "team_season": 0,
        "pbp": 0,
        "shots": 0,
        "errors": [],
    }

    # 1. Schedule
    print(f"Fetching ACB schedule for {season}...")
    try:
        schedule = acb.fetch_acb_schedule(season=season)
        if not schedule.empty:
            path = output_dir / f"schedule_{season}.parquet"
            schedule.to_parquet(path, index=False)
            summary["schedule"] = len(schedule)
            print(f"  Saved {len(schedule)} games to {path}")
        else:
            print("  No schedule data")
            summary["errors"].append("Schedule: empty")
    except Exception as e:
        print(f"  ERROR: {e}")
        summary["errors"].append(f"Schedule: {type(e).__name__}")
        schedule = pd.DataFrame()

    # 2. Player season stats
    print("Fetching ACB player season stats...")
    try:
        df = acb.fetch_acb_player_season(season=season)
        if not df.empty:
            path = output_dir / f"player_season_{season}.parquet"
            df.to_parquet(path, index=False)
            summary["player_season"] = len(df)
            print(f"  Saved {len(df)} player records to {path}")
        else:
            print("  No player season data")
    except Exception as e:
        print(f"  ERROR: {e}")
        summary["errors"].append(f"Player season: {type(e).__name__}")

    # 3. Team season stats
    print("Fetching ACB team season stats...")
    try:
        df = acb.fetch_acb_team_season(season=season)
        if not df.empty:
            path = output_dir / f"team_season_{season}.parquet"
            df.to_parquet(path, index=False)
            summary["team_season"] = len(df)
            print(f"  Saved {len(df)} team records to {path}")
        else:
            print("  No team season data")
    except Exception as e:
        print(f"  ERROR: {e}")
        summary["errors"].append(f"Team season: {type(e).__name__}")

    # 4. Per-game box scores
    if not schedule.empty:
        print(f"Fetching ACB box scores for {len(schedule)} games...")

        # Find game ID column
        game_id_col = None
        for col in ["game_code", "game_id", "GAME_ID", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col:
            all_player_games = []
            all_team_games = []
            errors = 0

            for idx, row in schedule.iterrows():
                game_id = str(row[game_id_col])

                try:
                    box = acb.fetch_acb_box_score(game_id)
                    if not box.empty:
                        box["GAME_ID"] = game_id
                        all_player_games.append(box)

                        # Aggregate to team level
                        if "TEAM" in box.columns or "team" in box.columns:
                            team_col = "TEAM" if "TEAM" in box.columns else "team"
                            team_agg = box.groupby(team_col).sum(numeric_only=True).reset_index()
                            team_agg["GAME_ID"] = game_id
                            all_team_games.append(team_agg)
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Game {game_id}: {type(e).__name__}")

                # Progress indicator
                if (idx + 1) % 50 == 0:
                    print(f"  Processed {idx + 1}/{len(schedule)} games...")

            # Save player game
            if all_player_games:
                df = pd.concat(all_player_games, ignore_index=True)
                path = output_dir / f"player_game_{season}.parquet"
                df.to_parquet(path, index=False)
                summary["player_game"] = len(df)
                print(f"  Saved {len(df)} player game records to {path}")

            # Save team game
            if all_team_games:
                df = pd.concat(all_team_games, ignore_index=True)
                path = output_dir / f"team_game_{season}.parquet"
                df.to_parquet(path, index=False)
                summary["team_game"] = len(df)
                print(f"  Saved {len(df)} team game records to {path}")

            if errors > 0:
                summary["errors"].append(f"Box scores: {errors} failed")
        else:
            print("  No game ID column found in schedule")

    # 5. PBP via BAwiR (if available and not skipped)
    rpy2_available = getattr(acb, "RPY2_AVAILABLE", False)

    if not skip_pbp:
        if rpy2_available:
            print("Fetching ACB play-by-play via BAwiR...")
            try:
                df = acb.fetch_acb_pbp_bawir(season=season)
                if not df.empty:
                    path = output_dir / f"pbp_{season}.parquet"
                    df.to_parquet(path, index=False)
                    summary["pbp"] = len(df)
                    print(f"  Saved {len(df)} PBP events to {path}")
                else:
                    print("  No PBP data from BAwiR")
            except Exception as e:
                print(f"  ERROR: {e}")
                summary["errors"].append(f"PBP: {type(e).__name__}")
        else:
            print("Skipping PBP: rpy2/BAwiR not available")
            summary["pbp"] = "rpy2_missing"
    else:
        print("Skipping PBP (--skip-pbp)")

    # 6. Shots via BAwiR (if available and not skipped)
    if not skip_shots:
        if rpy2_available:
            print("Fetching ACB shot charts via BAwiR...")
            try:
                df = acb.fetch_acb_shot_chart_bawir(season=season)
                if not df.empty:
                    path = output_dir / f"shots_{season}.parquet"
                    df.to_parquet(path, index=False)
                    summary["shots"] = len(df)
                    print(f"  Saved {len(df)} shots to {path}")
                else:
                    print("  No shot data from BAwiR")
            except Exception as e:
                print(f"  ERROR: {e}")
                summary["errors"].append(f"Shots: {type(e).__name__}")
        else:
            print("Skipping shots: rpy2/BAwiR not available")
            summary["shots"] = "rpy2_missing"
    else:
        print("Skipping shots (--skip-shots)")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Ingest ACB season data")
    parser.add_argument("--season", default="2024", help="Season to ingest (default: 2024)")
    parser.add_argument("--output", default="data/raw/acb", help="Output directory")
    parser.add_argument("--skip-pbp", action="store_true", help="Skip play-by-play ingestion")
    parser.add_argument("--skip-shots", action="store_true", help="Skip shot chart ingestion")
    args = parser.parse_args()

    print("=" * 70)
    print(f"ACB SEASON INGESTION: {args.season}")
    print("=" * 70)
    print()

    start = time.time()

    summary = ingest_acb_season(
        season=args.season,
        output_dir=Path(args.output),
        skip_pbp=args.skip_pbp,
        skip_shots=args.skip_shots,
    )

    elapsed = time.time() - start

    print()
    print("=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"Season: {summary['season']}")
    print(f"Schedule: {summary['schedule']} games")
    print(f"Player game: {summary['player_game']} records")
    print(f"Team game: {summary['team_game']} records")
    print(f"Player season: {summary['player_season']} records")
    print(f"Team season: {summary['team_season']} records")
    print(f"PBP: {summary['pbp']}")
    print(f"Shots: {summary['shots']}")

    if summary["errors"]:
        print()
        print("Errors:")
        for err in summary["errors"]:
            print(f"  - {err}")

    print()
    print(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
