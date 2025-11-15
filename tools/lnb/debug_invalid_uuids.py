#!/usr/bin/env python3
"""Deep debugging of invalid UUIDs

Systematically investigates why certain UUIDs don't return data from Atrium API.

This script:
1. Tests each invalid UUID individually
2. Captures the raw API response (not just empty/not empty)
3. Examines response structure to understand why it's empty
4. Checks for patterns in working vs non-working UUIDs
5. Tests different API parameters and state values
"""

import io
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb import _create_atrium_state

# ==============================================================================
# INVALID UUIDS FROM 2022-2023 (9 failures)
# ==============================================================================

INVALID_UUIDS = [
    "1515cca4-67e6-11f0-908d-9d1d3a927139",
    "0d346b41-6715-11f0-b247-27e6e78614e1",
    "0d2989af-6715-11f0-b609-27e6e78614e1",
    "0d0c88fe-6715-11f0-9d9c-27e6e78614e1",
    "14fa0584-67e6-11f0-8cb3-9d1d3a927139",
    "0d225fad-6715-11f0-810f-27e6e78614e1",
    "0cfdeaf9-6715-11f0-87bc-27e6e78614e1",
    "0cf637f3-6715-11f0-b9ed-27e6e78614e1",
    "0d141f9e-6715-11f0-bf7e-27e6e78614e1",
]

# VALID UUID from 2022-2023 for comparison
VALID_UUID = "0d0504a0-6715-11f0-98ab-27e6e78614e1"

# VALID UUIDs from 2023-2024 for comparison
VALID_2023_2024 = [
    "3fcea9a1-1f10-11ee-a687-db190750bdda",
    "cc7e470e-11a0-11ed-8ef5-8d12cdc95909",
]

ATRIUM_API_URL = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail"

# ==============================================================================
# DEBUGGING FUNCTIONS
# ==============================================================================


def analyze_api_response(uuid: str, response_type: str = "pbp") -> dict:
    """Get and analyze raw API response for a UUID

    Args:
        uuid: Fixture UUID to test
        response_type: "pbp" or "shot_chart"

    Returns:
        Dict with analysis results
    """
    state = _create_atrium_state(uuid, response_type)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    params = {"fixtureId": uuid, "state": state}

    try:
        response = requests.get(ATRIUM_API_URL, params=params, headers=headers, timeout=10)

        # Get status code
        status_code = response.status_code

        # Try to parse JSON
        try:
            data = response.json()
        except Exception:
            return {
                "uuid": uuid,
                "status_code": status_code,
                "error": "Failed to parse JSON",
                "raw_response": response.text[:200],
            }

        # Analyze response structure
        analysis = {
            "uuid": uuid,
            "status_code": status_code,
            "response_type": response_type,
            "top_level_keys": list(data.keys()) if isinstance(data, dict) else None,
            "has_data_key": "data" in data if isinstance(data, dict) else False,
        }

        # Deep dive into data structure
        if isinstance(data, dict) and "data" in data:
            data_obj = data["data"]
            analysis["data_keys"] = list(data_obj.keys()) if isinstance(data_obj, dict) else None

            # Check for PBP data
            if response_type == "pbp":
                pbp_data = data_obj.get("pbp", {})
                analysis["has_pbp"] = bool(pbp_data)
                analysis["pbp_keys"] = list(pbp_data.keys()) if isinstance(pbp_data, dict) else None

                # Count periods/events
                if isinstance(pbp_data, dict):
                    periods = pbp_data.get("periods", [])
                    if periods:
                        analysis["num_periods"] = len(periods)
                        total_events = sum(len(p.get("events", [])) for p in periods)
                        analysis["total_events"] = total_events
                    else:
                        analysis["num_periods"] = 0
                        analysis["total_events"] = 0
                        analysis["pbp_data_structure"] = str(pbp_data)[:200]

            # Check for shot chart data
            elif response_type == "shot_chart":
                shot_data = data_obj.get("shotChart", {})
                analysis["has_shot_chart"] = bool(shot_data)
                analysis["shot_chart_keys"] = (
                    list(shot_data.keys()) if isinstance(shot_data, dict) else None
                )

                if isinstance(shot_data, dict):
                    shots = shot_data.get("shots", [])
                    analysis["num_shots"] = len(shots) if isinstance(shots, list) else 0

        return analysis

    except Exception as e:
        return {"uuid": uuid, "error": str(e), "error_type": type(e).__name__}


def compare_uuid_patterns(valid_uuids: list, invalid_uuids: list) -> dict:
    """Analyze patterns between valid and invalid UUIDs

    Args:
        valid_uuids: List of working UUIDs
        invalid_uuids: List of non-working UUIDs

    Returns:
        Dict with pattern analysis
    """

    def extract_uuid_parts(uuid: str) -> dict:
        """Extract UUID components for analysis"""
        parts = uuid.split("-")
        return {
            "uuid": uuid,
            "part1": parts[0],
            "part2": parts[1],
            "part3": parts[2],  # Time/version component
            "part4": parts[3],
            "part5": parts[4],
            "full": uuid,
        }

    valid_patterns = [extract_uuid_parts(u) for u in valid_uuids]
    invalid_patterns = [extract_uuid_parts(u) for u in invalid_uuids]

    # Find common prefixes
    valid_part2s = {p["part2"] for p in valid_patterns}
    invalid_part2s = {p["part2"] for p in invalid_patterns}

    valid_part3s = {p["part3"] for p in valid_patterns}
    invalid_part3s = {p["part3"] for p in invalid_patterns}

    return {
        "valid_part2_unique": valid_part2s,
        "invalid_part2_unique": invalid_part2s,
        "valid_part3_unique": valid_part3s,
        "invalid_part3_unique": invalid_part3s,
        "part2_overlap": valid_part2s & invalid_part2s,
        "part3_overlap": valid_part3s & invalid_part3s,
    }


# ==============================================================================
# MAIN DEBUGGING
# ==============================================================================


def main():
    print("=" * 80)
    print("LNB INVALID UUID DEEP DEBUGGING")
    print("=" * 80)
    print()
    print("Goal: Understand WHY 9/10 UUIDs from 2022-2023 don't return data")
    print()

    # Step 1: Test a known valid UUID first (baseline)
    print("\n" + "=" * 80)
    print("STEP 1: BASELINE - Test Known Valid UUID")
    print("=" * 80)
    print()

    print(f"Testing valid UUID: {VALID_UUID}")
    valid_result = analyze_api_response(VALID_UUID, "pbp")

    print("\nValid UUID Response Structure:")
    print(json.dumps(valid_result, indent=2, default=str))

    # Step 2: Test one invalid UUID in detail
    print("\n" + "=" * 80)
    print("STEP 2: DETAILED ANALYSIS - Single Invalid UUID")
    print("=" * 80)
    print()

    test_invalid = INVALID_UUIDS[0]
    print(f"Testing invalid UUID: {test_invalid}")
    invalid_result = analyze_api_response(test_invalid, "pbp")

    print("\nInvalid UUID Response Structure:")
    print(json.dumps(invalid_result, indent=2, default=str))

    # Step 3: Compare response structures
    print("\n" + "=" * 80)
    print("STEP 3: COMPARISON - Valid vs Invalid")
    print("=" * 80)
    print()

    if valid_result.get("top_level_keys") == invalid_result.get("top_level_keys"):
        print("✅ Both have same top-level keys")
    else:
        print("❌ Different top-level keys:")
        print(f"   Valid:   {valid_result.get('top_level_keys')}")
        print(f"   Invalid: {invalid_result.get('top_level_keys')}")

    if valid_result.get("data_keys") == invalid_result.get("data_keys"):
        print("✅ Both have same data keys")
    else:
        print("❌ Different data keys:")
        print(f"   Valid:   {valid_result.get('data_keys')}")
        print(f"   Invalid: {invalid_result.get('data_keys')}")

    # Step 4: Test all invalid UUIDs
    print("\n" + "=" * 80)
    print("STEP 4: BATCH TEST - All Invalid UUIDs")
    print("=" * 80)
    print()

    results = []
    for uuid in INVALID_UUIDS:
        print(f"Testing {uuid[:30]}... ", end="")
        result = analyze_api_response(uuid, "pbp")

        if result.get("total_events", 0) > 0:
            print(f"✅ Has data! ({result['total_events']} events)")
        elif result.get("has_pbp"):
            print("⚠️  Has PBP structure but 0 events")
        elif result.get("has_data_key"):
            print("❌ Has data key but no PBP")
        else:
            print("❌ No data key")

        results.append(result)

    # Step 5: UUID pattern analysis
    print("\n" + "=" * 80)
    print("STEP 5: PATTERN ANALYSIS - UUID Structure")
    print("=" * 80)
    print()

    all_valid = [VALID_UUID] + VALID_2023_2024
    patterns = compare_uuid_patterns(all_valid, INVALID_UUIDS)

    print("UUID Part 2 (time-low):")
    print(f"  Valid UUIDs use:   {sorted(patterns['valid_part2_unique'])}")
    print(f"  Invalid UUIDs use: {sorted(patterns['invalid_part2_unique'])}")
    print(f"  Overlap:           {sorted(patterns['part2_overlap'])}")
    print()

    print("UUID Part 3 (time-mid/version):")
    print(f"  Valid UUIDs use:   {sorted(patterns['valid_part3_unique'])}")
    print(f"  Invalid UUIDs use: {sorted(patterns['invalid_part3_unique'])}")
    print(f"  Overlap:           {sorted(patterns['part3_overlap'])}")

    # Step 6: Save detailed results
    print("\n" + "=" * 80)
    print("STEP 6: SAVE DETAILED RESULTS")
    print("=" * 80)
    print()

    output_file = Path(__file__).parent / "debug_results_invalid_uuids.json"

    debug_output = {
        "timestamp": datetime.now().isoformat(),
        "valid_baseline": valid_result,
        "invalid_sample": invalid_result,
        "all_invalid_results": results,
        "pattern_analysis": {
            "valid_part2": list(patterns["valid_part2_unique"]),
            "invalid_part2": list(patterns["invalid_part2_unique"]),
            "valid_part3": list(patterns["valid_part3_unique"]),
            "invalid_part3": list(patterns["invalid_part3_unique"]),
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(debug_output, f, indent=2, default=str)

    print(f"✅ Saved detailed results to: {output_file.name}")

    # Step 7: Summary and hypothesis
    print("\n" + "=" * 80)
    print("STEP 7: SUMMARY & HYPOTHESIS")
    print("=" * 80)
    print()

    print("Key Findings:")
    print(f"1. Valid UUID returns {valid_result.get('total_events', 0)} events")
    print(f"2. Invalid UUID returns {invalid_result.get('total_events', 0)} events")
    print(
        f"3. Both have {'same' if valid_result.get('data_keys') == invalid_result.get('data_keys') else 'different'} response structure"
    )
    print()

    print("Possible Explanations:")
    print("  1. Games haven't been played yet (future games)")
    print("  2. Games are from different competition (not Pro A)")
    print("  3. Atrium API doesn't have historical data for these games")
    print("  4. UUIDs were extracted incorrectly from LNB website")
    print()

    print("Next Steps:")
    print("  1. Check LNB website directly for these UUIDs")
    print("  2. Verify game dates (are they in the future?)")
    print("  3. Check competition type (Pro A vs other divisions)")
    print("  4. Test if LNB API has match details for these UUIDs")


if __name__ == "__main__":
    main()
