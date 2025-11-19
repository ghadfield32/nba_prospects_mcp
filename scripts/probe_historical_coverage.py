#!/usr/bin/env python
"""Historical Coverage Probe - All Leagues

Systematically tests data availability across all leagues and seasons.
Generates a comprehensive data availability matrix.

Usage:
    python scripts/probe_historical_coverage.py
    python scripts/probe_historical_coverage.py --league acb
    python scripts/probe_historical_coverage.py --output coverage_matrix.csv

Output:
    - Console summary
    - Optional CSV matrix
"""

import argparse
import sys
import time

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd


def probe_acb_coverage():
    """Probe ACB data availability across seasons.

    Rules:
      - Uses fetch_acb_schedule (cleaned of synthetic rows).
      - Uses player/team *season* stats only.
      - Does NOT fabricate per-game PBP/shot counts.
      - If rpy2/BAwiR are unavailable, PBP/shots are marked 'rpy2_missing'.
    """
    from cbb_data.fetchers import acb

    results = []
    seasons = ["2024", "2023", "2022", "2021", "2020", "2019"]

    for season in seasons:
        row = {
            "league": "ACB",
            "season": season,
            "schedule": 0,
            "player_game": "N/A",  # ACB uses per-game fetch_acb_box_score
            "team_game": "N/A",  # ACB uses per-game fetch_acb_box_score
            "player_season": 0,
            "team_season": 0,
            "pbp": "NotProbed",
            "shots": "NotProbed",
        }

        # Schedule (game index) - now cleaned of synthetic rows
        try:
            df = acb.fetch_acb_schedule(season=season)
            if df is not None and not df.empty:
                if "GAME_ID" in df.columns:
                    row["schedule"] = int(df["GAME_ID"].nunique())
                else:
                    row["schedule"] = len(df)
            else:
                row["schedule"] = 0
        except Exception as e:
            row["schedule"] = f"Err({type(e).__name__})"

        # Player season stats
        try:
            df = acb.fetch_acb_player_season(season=season)
            row["player_season"] = 0 if df is None or df.empty else len(df)
        except Exception as e:
            row["player_season"] = f"Err({type(e).__name__})"

        # Team season stats
        try:
            df = acb.fetch_acb_team_season(season=season)
            row["team_season"] = 0 if df is None or df.empty else len(df)
        except Exception as e:
            row["team_season"] = f"Err({type(e).__name__})"

        # PBP / shots via BAwiR (optional; do NOT fabricate)
        try:
            # Check if BAwiR functions exist and rpy2 is available
            if hasattr(acb, "fetch_acb_pbp_bawir") and getattr(acb, "RPY2_AVAILABLE", False):
                row["pbp"] = "OK(BAwiR)"
                row["shots"] = "OK(BAwiR)"
            else:
                row["pbp"] = "rpy2_missing"
                row["shots"] = "rpy2_missing"
        except Exception as e:
            row["pbp"] = f"Err({type(e).__name__})"
            row["shots"] = f"Err({type(e).__name__})"

        results.append(row)
        print(
            f"  ACB {season}: schedule={row['schedule']}, player_season={row['player_season']}, pbp={row['pbp']}"
        )

    return results


def probe_nz_nbl_coverage():
    """Probe NZ-NBL schedule/box availability with explicit unavailability reasons.

    Rules:
      - Records explicit status (OK/NoGames/Forbidden/Err) instead of silent zeros
      - Distinguishes 403 errors from empty seasons
      - NZ-NBL season typically runs May-August
    """
    from cbb_data.fetchers import DataUnavailableError, nz_nbl_fiba

    results = []
    seasons = ["2024", "2023", "2022", "2021"]

    for season in seasons:
        row = {
            "league": "NZ-NBL",
            "season": season,
            "schedule": 0,
            "player_game": 0,
            "team_game": 0,
            "player_season": 0,
            "team_season": 0,
            "pbp": "NotProbed",
            "shots": "NotProbed",
            "status": "OK",
        }

        # Try schedule first
        try:
            df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season=season)
            row["schedule"] = 0 if df is None or df.empty else len(df)
        except Exception as e:
            if isinstance(e, DataUnavailableError):
                if e.kind == "no_games_for_season":
                    row["status"] = "NoGames"
                elif e.kind == "access_forbidden":
                    row["status"] = "Forbidden"
                else:
                    row["status"] = f"Err({e.kind})"
            else:
                row["status"] = f"Err({type(e).__name__})"

        # Only try player/team data if schedule succeeded
        if row["status"] == "OK" and row["schedule"] > 0:
            try:
                df = nz_nbl_fiba.fetch_nz_nbl_player_game(season=season)
                row["player_game"] = 0 if df is None or df.empty else len(df)
            except Exception as e:
                if isinstance(e, DataUnavailableError):
                    row["player_game"] = f"Err({e.kind})"
                else:
                    row["player_game"] = f"Err({type(e).__name__})"

            try:
                df = nz_nbl_fiba.fetch_nz_nbl_team_game(season=season)
                row["team_game"] = 0 if df is None or df.empty else len(df)
            except Exception as e:
                if isinstance(e, DataUnavailableError):
                    row["team_game"] = f"Err({e.kind})"
                else:
                    row["team_game"] = f"Err({type(e).__name__})"

            try:
                df = nz_nbl_fiba.fetch_nz_nbl_player_season(season=season)
                row["player_season"] = 0 if df is None or df.empty else len(df)
            except Exception as e:
                row["player_season"] = f"Err({type(e).__name__})"

            try:
                df = nz_nbl_fiba.fetch_nz_nbl_team_season(season=season)
                row["team_season"] = 0 if df is None or df.empty else len(df)
            except Exception as e:
                row["team_season"] = f"Err({type(e).__name__})"

        results.append(row)
        print(
            f"  NZ-NBL {season}: status={row['status']}, schedule={row['schedule']}, player_game={row['player_game']}"
        )

    return results


def probe_lnb_coverage():
    """Probe LNB data availability across seasons.

    Note: LNB uses different season formats:
    - v2/API functions use int (e.g., 2025 for 2024-25 season)
    - Historical/season functions use string (e.g., "2024")
    """
    from cbb_data.fetchers import lnb

    results = []
    # Map display season to int/string formats
    seasons = [
        {"display": "2024-2025", "int": 2025, "str": "2024"},
        {"display": "2023-2024", "int": 2024, "str": "2023"},
        {"display": "2022-2023", "int": 2023, "str": "2022"},
        {"display": "2021-2022", "int": 2022, "str": "2021"},
    ]

    for season_info in seasons:
        season_display = season_info["display"]
        season_int = season_info["int"]
        season_str = season_info["str"]

        row = {
            "league": "LNB",
            "season": season_display,
            "schedule": 0,
            "player_game": 0,
            "team_game": 0,
            "player_season": 0,
            "team_season": 0,
            "pbp": 0,
            "shots": 0,
        }

        # Schedule via API v2 (uses int season)
        try:
            df = lnb.fetch_lnb_schedule_v2(season=season_int)
            row["schedule"] = len(df) if not df.empty else 0
        except Exception:
            row["schedule"] = "Err"

        # Player game (uses int season)
        try:
            df = lnb.fetch_lnb_player_game(season=season_int)
            row["player_game"] = len(df) if not df.empty else 0
        except Exception:
            row["player_game"] = "Err"

        # Team game normalized (uses string season)
        try:
            df = lnb.fetch_lnb_team_game_normalized(season=season_str)
            row["team_game"] = len(df) if not df.empty else 0
        except Exception:
            row["team_game"] = "Err"

        # Player season (uses string season)
        try:
            df = lnb.fetch_lnb_player_season(season=season_str)
            row["player_season"] = len(df) if not df.empty else 0
        except Exception:
            row["player_season"] = "Err"

        # Team season (uses string season)
        try:
            df = lnb.fetch_lnb_team_season(season=season_str)
            row["team_season"] = len(df) if not df.empty else 0
        except Exception:
            row["team_season"] = "Err"

        # PBP historical (uses string season)
        try:
            df = lnb.fetch_lnb_pbp_historical(season=season_str)
            row["pbp"] = len(df) if not df.empty else 0
        except Exception:
            row["pbp"] = "Err"

        # Shots historical (uses string season)
        try:
            df = lnb.fetch_lnb_shots_historical(season=season_str)
            row["shots"] = len(df) if not df.empty else 0
        except Exception:
            row["shots"] = "Err"

        results.append(row)
        print(
            f"  LNB {season_display}: schedule={row['schedule']}, player_game={row['player_game']}, pbp={row['pbp']}"
        )

    return results


def main():
    parser = argparse.ArgumentParser(description="Probe historical data coverage")
    parser.add_argument("--league", help="Specific league to probe (acb, nz-nbl, lnb)")
    parser.add_argument("--output", help="Output CSV file path")
    args = parser.parse_args()

    print("=" * 70)
    print("HISTORICAL COVERAGE PROBE")
    print("=" * 70)
    print()

    start = time.time()
    all_results = []

    # Probe each league
    if args.league is None or args.league.lower() == "acb":
        print("Probing ACB (Spanish Liga Endesa)...")
        all_results.extend(probe_acb_coverage())
        print()

    if args.league is None or args.league.lower() == "nz-nbl":
        print("Probing NZ-NBL (New Zealand NBL)...")
        all_results.extend(probe_nz_nbl_coverage())
        print()

    if args.league is None or args.league.lower() == "lnb":
        print("Probing LNB (French Pro A/Pro B)...")
        all_results.extend(probe_lnb_coverage())
        print()

    elapsed = time.time() - start

    # Create summary DataFrame
    df = pd.DataFrame(all_results)

    # Print summary
    print("=" * 70)
    print("COVERAGE MATRIX")
    print("=" * 70)
    print()
    print(df.to_string(index=False))
    print()

    # Save to CSV if requested
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved to: {args.output}")
        print()

    print(f"Completed in {elapsed:.1f}s")

    # Summary stats
    print()
    print("Summary:")
    for league in df["league"].unique():
        league_df = df[df["league"] == league]
        seasons_with_data = sum(
            1
            for _, row in league_df.iterrows()
            if isinstance(row["schedule"], int) and row["schedule"] > 0
        )
        print(f"  {league}: {seasons_with_data}/{len(league_df)} seasons with schedule data")


if __name__ == "__main__":
    main()
