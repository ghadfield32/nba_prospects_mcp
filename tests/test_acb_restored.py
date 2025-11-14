"""Test restored ACB fetcher with new URLs"""

from src.cbb_data.fetchers import acb

print("=" * 70)
print("TESTING RESTORED ACB FETCHER")
print("=" * 70)

# Test player season
print("\n[TEST 1] Fetching ACB player season stats (2024-25 season)")
print("-" * 70)
try:
    df_players = acb.fetch_acb_player_season(season="2024")
    print(f"[SUCCESS] Fetched {len(df_players)} player records")
    if not df_players.empty:
        print(f"   Columns: {list(df_players.columns)}")
        print("   First 5 players:")
        print(df_players.head())
    else:
        print("   [WARNING] DataFrame is empty")
except Exception as e:
    print(f"[ERROR] {e}")

# Test team season
print("\n\n[TEST 2] Fetching ACB team season/standings (2024-25 season)")
print("-" * 70)
try:
    df_teams = acb.fetch_acb_team_season(season="2024")
    print(f"[SUCCESS] Fetched {len(df_teams)} team records")
    if not df_teams.empty:
        print(f"   Columns: {list(df_teams.columns)}")
        print("   Standings:")
        print(df_teams.to_string())
    else:
        print("   [WARNING] DataFrame is empty")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
