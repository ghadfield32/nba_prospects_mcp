"""Summary validation for all data sources

This creates a summary report of all data sources that can be used.
"""


def test_espn_mbb():
    """Test ESPN MBB via sportsdataverse"""
    print("\n" + "=" * 70)
    print("Testing ESPN Men's Basketball (sportsdataverse)")
    print("=" * 70)

    try:
        from sportsdataverse.mbb import mbb_schedule, mbb_teams

        teams = mbb_teams()

        if teams is not None and not teams.empty:
            print(f"[OK] Fetched {len(teams)} teams")

            # Try schedule
            from datetime import datetime

            season = datetime.now().year + 1 if datetime.now().month >= 10 else datetime.now().year
            schedule = mbb_schedule(season=season)

            if schedule is not None and not schedule.empty:
                print(f"[OK] Fetched {len(schedule)} games for season {season}")
                print("[OK] ESPN MBB: FREE, ACCESSIBLE, COMPLETE")
                return True
            else:
                print("[WARN] Schedule data limited")
                return False
        else:
            print("[FAIL] No team data")
            return False

    except ImportError:
        print("[SKIP] sportsdataverse not installed")
        print("      Install with: uv pip install sportsdataverse")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_euroleague():
    """Test EuroLeague API"""
    print("\n" + "=" * 70)
    print("Testing EuroLeague API")
    print("=" * 70)

    try:
        from euroleague_api.season_data import SeasonData

        # Try to fetch recent season
        season_data = SeasonData("E2024")
        games = season_data.get_games_range(1, 5)

        if games:
            print(f"[OK] Fetched {len(games)} games")
            print("[OK] EuroLeague API: FREE, ACCESSIBLE, COMPLETE")
            return True
        else:
            print("[WARN] No game data")
            return False

    except ImportError:
        print("[SKIP] euroleague-api not installed")
        print("      Install with: uv pip install euroleague-api")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    """Run all source validations"""
    print("=" * 70)
    print("BASKETBALL DATA SOURCES VALIDATION")
    print("=" * 70)

    results = {}

    # Test each source
    results["ESPN MBB"] = test_espn_mbb()
    results["EuroLeague"] = test_euroleague()

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    for source, passed in results.items():
        status = "[OK]" if passed else "[FAIL/SKIP]"
        print(f"{status:12} {source}")

    print("=" * 70)

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    print(f"\nPassed: {passed_count}/{total_count} sources")

    if passed_count > 0:
        print("\nRECOMMENDATION: Use validated sources for data pipeline")
        return True
    else:
        print("\nWARNING: No sources validated successfully")
        return False


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
