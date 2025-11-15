#!/usr/bin/env python3
"""Test historical UUIDs from fixture_uuids_by_season.json

This script tests the UUIDs we already have from previous discovery
to see if they have PBP/shot data available.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_atrium import (
    fetch_fixture_detail_and_pbp,
    parse_fixture_metadata,
    parse_pbp_events,
    parse_shots_from_pbp,
)


def main():
    # Load known UUIDs
    uuid_file = Path("tools/lnb/fixture_uuids_by_season.json")

    with open(uuid_file) as f:
        data = json.load(f)

    print(f"\n{'='*70}")
    print("Testing Historical UUIDs for PBP/Shot Data")
    print(f"{'='*70}\n")

    for season, uuids in data["mappings"].items():
        print(f"\nSeason: {season}")
        print(f"UUIDs to test: {len(uuids)}")

        for idx, uuid in enumerate(uuids, 1):
            print(f"\n  [{idx}/{len(uuids)}] Testing {uuid}...")

            try:
                # Fetch
                payload = fetch_fixture_detail_and_pbp(uuid)

                # Parse metadata
                metadata = parse_fixture_metadata(payload)
                print(f"      Game: {metadata.home_team_name} vs {metadata.away_team_name}")
                print(f"      Score: {metadata.home_score}-{metadata.away_score}")
                print(f"      Date: {metadata.start_time_local}")

                # Parse PBP
                pbp_events = parse_pbp_events(payload, uuid)
                print(f"      PBP Events: {len(pbp_events)}")

                if pbp_events:
                    periods = {e.period_id for e in pbp_events}
                    print(f"      Periods: {sorted(periods)}")

                    # Parse shots
                    shots = parse_shots_from_pbp(pbp_events)
                    print(f"      Shots: {len(shots)} total")

                    if shots:
                        made = sum(1 for s in shots if s.made)
                        print(f"             {made} made, {len(shots)-made} missed")
                        print("      [OK] HAS PBP + SHOTS DATA")
                    else:
                        print("      [WARN] Has PBP but no shots")

                # Check if pbp key exists in payload
                pbp_in_payload = "pbp" in payload
                print(f"      'pbp' key in response: {pbp_in_payload}")

                if pbp_in_payload:
                    pbp_keys = list(payload.get("pbp", {}).keys())
                    print(f"      PBP period keys: {pbp_keys}")

            except Exception as e:
                print(f"      [ERROR]: {e}")


if __name__ == "__main__":
    main()
