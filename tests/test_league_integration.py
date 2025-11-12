"""Test League Integration - Verify 6 New Leagues Registered

This script validates that the 6 new leagues (EuroCup, G-League, CEBL, OTE, NJCAA, NAIA)
are properly registered in the DatasetRegistry and accessible via the API.

Expected Results:
- All 7 datasets should list the 9 supported leagues
- DatasetRegistry.filter_by_league() should return datasets for new leagues
- Metadata should show correct sources for each league

Test Scope:
✅ Dataset registration metadata
✅ League filtering functionality
✅ Source attribution
❌ Live data fetching (not needed for this test)
"""

import sys

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, "src")

from cbb_data.catalog.registry import DatasetRegistry

# Target leagues to validate
NEW_LEAGUES = ["EuroCup", "G-League", "CEBL", "OTE", "NJCAA", "NAIA"]
ALL_LEAGUES = ["NCAA-MBB", "NCAA-WBB", "EuroLeague"] + NEW_LEAGUES

# All datasets that should support the new leagues
ALL_DATASETS = [
    "schedule",
    "player_game",
    "team_game",
    "pbp",
    "shots",
    "player_season",
    "team_season",
]

print("=" * 80)
print("LEAGUE INTEGRATION TEST - Dataset Registry Validation")
print("=" * 80)

# Test 1: Verify all datasets are registered
print("\n[TEST 1] Checking dataset registrations...")
all_dataset_ids = [info.id for info in DatasetRegistry.list_infos()]
print(f"Registered datasets: {all_dataset_ids}")

missing_datasets = [ds for ds in ALL_DATASETS if ds not in all_dataset_ids]
if missing_datasets:
    print(f"❌ FAIL: Missing datasets: {missing_datasets}")
else:
    print("✅ PASS: All 7 datasets registered")

# Test 2: Verify each dataset supports all 9 leagues
print("\n[TEST 2] Checking league support per dataset...")
failures = []

for dataset_id in ALL_DATASETS:
    # Get dataset metadata dict
    dataset_dict = DatasetRegistry.get(dataset_id)
    dataset_leagues = dataset_dict["leagues"]

    print(f"\n{dataset_id}:")
    print(f"  Registered leagues: {dataset_leagues}")

    # Check if all 9 leagues are present
    missing_leagues = [league for league in ALL_LEAGUES if league not in dataset_leagues]

    if missing_leagues:
        print(f"  ❌ Missing leagues: {missing_leagues}")
        failures.append(f"{dataset_id} missing {missing_leagues}")
    else:
        print("  ✅ All 9 leagues supported")

    # Check sources
    print(f"  Sources: {dataset_dict['sources']}")

if failures:
    print(f"\n❌ FAIL: {len(failures)} datasets missing leagues")
    for failure in failures:
        print(f"  - {failure}")
else:
    print("\n✅ PASS: All datasets support all 9 leagues")

# Test 3: Verify filter_by_league works for new leagues
print("\n[TEST 3] Testing DatasetRegistry.filter_by_league()...")
filter_failures = []

for league in NEW_LEAGUES:
    matching_datasets = DatasetRegistry.filter_by_league(league)
    matching_ids = [info.id for info in matching_datasets]

    print(f"\n{league}:")
    print(f"  Datasets: {matching_ids}")

    # Should match all 7 datasets
    if len(matching_ids) != len(ALL_DATASETS):
        missing = [ds for ds in ALL_DATASETS if ds not in matching_ids]
        print(f"  ❌ Expected {len(ALL_DATASETS)} datasets, got {len(matching_ids)}")
        print(f"     Missing: {missing}")
        filter_failures.append(f"{league} missing {missing}")
    else:
        print(f"  ✅ All {len(ALL_DATASETS)} datasets match")

if filter_failures:
    print(f"\n❌ FAIL: {len(filter_failures)} leagues have incomplete filter results")
    for failure in filter_failures:
        print(f"  - {failure}")
else:
    print("\n✅ PASS: filter_by_league() works for all new leagues")

# Test 4: Verify source attribution
print("\n[TEST 4] Checking source attribution...")
expected_sources = {
    "schedule": ["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
    "player_game": ["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
    "team_game": ["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
    "pbp": ["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
    "shots": ["CBBpy", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
    "player_season": ["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
    "team_season": ["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports"],
}

source_failures = []
for dataset_id, expected in expected_sources.items():
    dataset_dict = DatasetRegistry.get(dataset_id)
    actual = dataset_dict["sources"]

    if set(actual) != set(expected):
        print(f"\n{dataset_id}:")
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        if missing:
            print(f"  ❌ Missing sources: {missing}")
        if extra:
            print(f"  ⚠️  Extra sources: {extra}")
        source_failures.append(dataset_id)
    else:
        print(f"✅ {dataset_id}: Sources correct")

if source_failures:
    print(f"\n⚠️  WARNING: {len(source_failures)} datasets have incorrect sources")
else:
    print("\n✅ PASS: All source attributions correct")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_tests = 4
failed_tests = sum(
    [
        1 if missing_datasets else 0,
        1 if failures else 0,
        1 if filter_failures else 0,
        1 if source_failures else 0,
    ]
)

print(f"Tests passed: {total_tests - failed_tests}/{total_tests}")

if failed_tests == 0:
    print("\n✅ ALL TESTS PASSED - League integration successful!")
    print("🎉 6 new leagues (EuroCup, G-League, CEBL, OTE, NJCAA, NAIA) now accessible via API/MCP")
else:
    print(f"\n⚠️  {failed_tests} test(s) failed - see errors above")

print("=" * 80)
