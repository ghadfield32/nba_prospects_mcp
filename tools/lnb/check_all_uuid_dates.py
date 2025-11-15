#!/usr/bin/env python3
"""Check match dates and status for all UUIDs

This will reveal if the "invalid" UUIDs are actually future games.
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

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_endpoints import LNB_API

# All UUIDs from our file
ALL_UUIDS = {
    "2022-2023 (labeled in file)": [
        "1515cca4-67e6-11f0-908d-9d1d3a927139",
        "0d0504a0-6715-11f0-98ab-27e6e78614e1",  # This one works!
        "0d346b41-6715-11f0-b247-27e6e78614e1",
        "0d2989af-6715-11f0-b609-27e6e78614e1",
        "0d0c88fe-6715-11f0-9d9c-27e6e78614e1",
        "14fa0584-67e6-11f0-8cb3-9d1d3a927139",
        "0d225fad-6715-11f0-810f-27e6e78614e1",
        "0cfdeaf9-6715-11f0-87bc-27e6e78614e1",
        "0cf637f3-6715-11f0-b9ed-27e6e78614e1",
        "0d141f9e-6715-11f0-bf7e-27e6e78614e1",
    ],
    "2023-2024 (labeled in file)": [
        "3fcea9a1-1f10-11ee-a687-db190750bdda",
        "cc7e470e-11a0-11ed-8ef5-8d12cdc95909",
        "7d414bce-f5da-11eb-b3fd-a23ac5ab90da",
        "0cac6e1b-6715-11f0-a9f3-27e6e78614e1",
        "0cd1323f-6715-11f0-86f4-27e6e78614e1",
    ],
    "2024-2025 (labeled in file)": [
        "0cac6e1b-6715-11f0-a9f3-27e6e78614e1",
        "0cd1323f-6715-11f0-86f4-27e6e78614e1",
        "0ce02919-6715-11f0-9d01-27e6e78614e1",
        "0d0504a0-6715-11f0-98ab-27e6e78614e1",
    ],
}


def get_match_info(uuid: str) -> dict:
    """Get match date and status"""
    url = LNB_API.match_details(uuid)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            match_data = data.get("data", {})

            return {
                "uuid": uuid,
                "date": match_data.get("match_date"),
                "status": match_data.get("match_status"),
                "round": match_data.get("round_description"),
                "competition": match_data.get("competition_name"),
            }
    except Exception:
        pass

    return {"uuid": uuid, "date": None, "status": None}


print("=" * 80)
print("UUID DATE AND STATUS CHECK")
print("=" * 80)
print()
print("Checking ACTUAL game dates for all UUIDs...")
print(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")
print()

all_results = []

for season_label, uuids in ALL_UUIDS.items():
    print(f"\n{season_label}:")
    print("-" * 80)

    for uuid in uuids:
        info = get_match_info(uuid)

        date_str = info.get("date", "Unknown")
        status = info.get("status", "Unknown")
        round_desc = info.get("round", "")

        # Determine if future/past
        time_status = ""
        if date_str and date_str != "Unknown":
            try:
                match_date = datetime.fromisoformat(date_str)
                now = datetime.now()

                if match_date > now:
                    days_until = (match_date - now).days
                    time_status = f"FUTURE (+{days_until}d)"
                else:
                    days_ago = (now - match_date).days
                    time_status = f"PAST (-{days_ago}d)"
            except Exception:
                time_status = "?"

        # Status indicator
        status_icon = "✅" if status == "COMPLETE" else ("🕐" if status == "SCHEDULED" else "❓")

        print(
            f"  {status_icon} {uuid[:35]} | {date_str} | {status:10s} | {time_status:15s} | {round_desc}"
        )

        all_results.append(
            {
                "labeled_season": season_label,
                "uuid": uuid,
                "actual_date": date_str,
                "status": status,
                "time_status": time_status,
            }
        )

# Analysis
print()
print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print()

# Group by status
complete = [r for r in all_results if r["status"] == "COMPLETE"]
scheduled = [r for r in all_results if r["status"] == "SCHEDULED"]
unknown = [r for r in all_results if r["status"] not in ["COMPLETE", "SCHEDULED"]]

print(f"Total UUIDs: {len(all_results)}")
print(f"  COMPLETE (played): {len(complete)}")
print(f"  SCHEDULED (future): {len(scheduled)}")
print(f"  Unknown: {len(unknown)}")
print()

if scheduled:
    print(f"⚠️  {len(scheduled)} UUIDs are FUTURE GAMES (not yet played):")
    for r in scheduled:
        print(f"   - {r['uuid'][:35]} (labeled as '{r['labeled_season']}')")
    print()
    print("   These won't have PBP data until after they're played!")

# Check for mislabeled seasons
print()
print("SEASON LABEL VERIFICATION:")
print()

# Check if UUIDs labeled as 2022-2023 are actually from 2024-2025
mislabeled_2022 = [
    r
    for r in all_results
    if "2022-2023" in r["labeled_season"]
    and r["actual_date"]
    and r["actual_date"].startswith("2024")
]

if mislabeled_2022:
    print(
        f"❌ Found {len(mislabeled_2022)} UUIDs mislabeled as 2022-2023 but are actually 2024-2025:"
    )
    for r in mislabeled_2022:
        print(f"   {r['uuid'][:35]} | Actual date: {r['actual_date']}")

# Save results
output_file = Path(__file__).parent / "uuid_date_analysis.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=2)

print()
print(f"Detailed results saved to: {output_file.name}")
