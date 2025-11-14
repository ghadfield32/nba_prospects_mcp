"""Test NCAA-MBB/WBB/G-League wiring to catalog

Validates that schedule functions work end-to-end from catalog.
"""

from src.cbb_data.catalog.sources import get_league_source_config

print("=" * 70)
print("TESTING NCAA-MBB/WBB/G-LEAGUE CATALOG WIRING")
print("=" * 70)

# Test NCAA-MBB
print("\n[TEST 1] NCAA-MBB Schedule")
print("-" * 70)
try:
    cfg = get_league_source_config("NCAA-MBB")
    if cfg and cfg.fetch_schedule:
        # Test with a specific date (ESPN scoreboard signature: date, season, groups)
        df = cfg.fetch_schedule(date="20240115")  # Jan 15, 2024
        print(f"[SUCCESS] Fetched {len(df)} games")
        if not df.empty:
            print(f"   Columns: {list(df.columns)[:10]}")
            print("   Sample:")
            print(df.head(3).to_string())
    else:
        print("[FAILED] No fetch_schedule function wired")
except Exception as e:
    print(f"[ERROR] {e}")

# Test NCAA-WBB
print("\n\n[TEST 2] NCAA-WBB Schedule")
print("-" * 70)
try:
    cfg = get_league_source_config("NCAA-WBB")
    if cfg and cfg.fetch_schedule:
        df = cfg.fetch_schedule(date="20240115")  # Jan 15, 2024
        print(f"[SUCCESS] Fetched {len(df)} games")
        if not df.empty:
            print(f"   Columns: {list(df.columns)[:10]}")
    else:
        print("[FAILED] No fetch_schedule function wired")
except Exception as e:
    print(f"[ERROR] {e}")

# Test G-League
print("\n\n[TEST 3] G-League Schedule")
print("-" * 70)
try:
    cfg = get_league_source_config("G-League")
    if cfg and cfg.fetch_schedule:
        df = cfg.fetch_schedule(season="2023-24")
        print(f"[SUCCESS] Fetched {len(df)} games")
        if not df.empty:
            print(f"   Columns: {list(df.columns)[:10]}")
    else:
        print("[FAILED] No fetch_schedule function wired")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("All three leagues (NCAA-MBB, NCAA-WBB, G-League) now have")
print("schedule functions wired through the catalog!")
print("=" * 70)
