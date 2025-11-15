#!/usr/bin/env python3
"""LNB Boxscore cURL Template Generator

Generates ready-to-use cURL commands for testing potential boxscore endpoints.
Useful for quickly testing discovered endpoints from browser DevTools.

Usage:
    python tools/lnb/generate_curl_templates.py

Output:
    - Console: Formatted cURL commands
    - File: tools/lnb/curl_templates.txt (optional)
"""

from datetime import datetime

# Known test game IDs from schedule
KNOWN_GAME_IDS = [
    28931,  # Game from earlier in season
    28910,  # Another test game
    28914,  # Another test game
]

# Potential endpoint patterns
ENDPOINT_PATTERNS = [
    "/stats/getMatchBoxScore",
    "/api/match/{game_id}/boxscore",
    "/api/match/{game_id}/stats",
    "/api/games/{game_id}/boxscore",
    "/api/v1/match/{game_id}/boxscore",
    "/stats/match/{game_id}",
    "/boxscore/{game_id}",
]

# Base URL for LNB API
BASE_URL = "https://www.lnb.fr"


def generate_curl_command(endpoint: str, game_id: int, method: str = "GET") -> str:
    """Generate a cURL command for an endpoint.

    Args:
        endpoint: API endpoint path (may contain {game_id} placeholder)
        game_id: Game ID to test
        method: HTTP method (GET or POST)

    Returns:
        Formatted cURL command string
    """
    # Replace game_id placeholder
    full_url = f"{BASE_URL}{endpoint}".replace("{game_id}", str(game_id))

    # Build cURL command
    curl_parts = [
        f"curl -X {method}",
        f'"{full_url}"',
        '-H "Accept: application/json"',
        '-H "Content-Type: application/json"',
        '-H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"',
    ]

    # Add POST-specific options
    if method == "POST":
        curl_parts.append(f"-d '{{\"match_external_id\": {game_id}}}'")

    return " \\\n  ".join(curl_parts)


def generate_all_templates():
    """Generate all cURL templates and print to console."""
    print("=" * 80)
    print("  LNB Boxscore Endpoint - cURL Test Templates")
    print("=" * 80)
    print()
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Instructions:")
    print("  1. Copy a cURL command below")
    print("  2. Paste into terminal or browser DevTools console")
    print("  3. Check response structure")
    print("  4. Update test_lnb_boxscore_discovery.py with working endpoint")
    print()
    print("=" * 80)
    print()

    templates = []

    for game_id in KNOWN_GAME_IDS:
        print(f"\n{'='*80}")
        print(f"  GAME ID: {game_id}")
        print(f"{'='*80}\n")

        for i, endpoint in enumerate(ENDPOINT_PATTERNS, 1):
            print(f"[{i}] Endpoint: {endpoint}")
            print("-" * 80)

            # GET request
            curl_get = generate_curl_command(endpoint, game_id, "GET")
            print("\nGET Request:")
            print(curl_get)

            templates.append(
                {
                    "game_id": game_id,
                    "endpoint": endpoint,
                    "method": "GET",
                    "curl": curl_get,
                }
            )

            # POST request (if endpoint doesn't have game_id in path)
            if "{game_id}" not in endpoint:
                print("\nPOST Request (alternative):")
                curl_post = generate_curl_command(endpoint, game_id, "POST")
                print(curl_post)

                templates.append(
                    {
                        "game_id": game_id,
                        "endpoint": endpoint,
                        "method": "POST",
                        "curl": curl_post,
                    }
                )

            print()

    # Print summary
    print("\n" + "=" * 80)
    print("  CUSTOM ENDPOINT TEMPLATE")
    print("=" * 80)
    print()
    print("If you discovered a different endpoint pattern, use this template:")
    print()
    print("curl -X GET \\")
    print('  "https://www.lnb.fr/YOUR_ENDPOINT_HERE?match_id=28931" \\')
    print('  -H "Accept: application/json" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"')
    print()

    # Print quick reference
    print("\n" + "=" * 80)
    print("  QUICK REFERENCE - All Endpoints")
    print("=" * 80)
    print()
    for i, endpoint in enumerate(ENDPOINT_PATTERNS, 1):
        print(f"  [{i}] {endpoint}")
    print()
    print(f"  Known game IDs: {', '.join(map(str, KNOWN_GAME_IDS))}")
    print()

    return templates


def save_templates_to_file(templates):
    """Save templates to a text file.

    Args:
        templates: List of template dictionaries
    """
    from pathlib import Path

    output_file = Path(__file__).parent / "curl_templates.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("  LNB Boxscore Endpoint - cURL Test Templates\n")
        f.write("=" * 80 + "\n")
        f.write(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for template in templates:
            f.write(f"\n{'='*80}\n")
            f.write(f"Game ID: {template['game_id']}\n")
            f.write(f"Endpoint: {template['endpoint']}\n")
            f.write(f"Method: {template['method']}\n")
            f.write(f"{'='*80}\n\n")
            f.write(template["curl"] + "\n")

    print(f"\n[INFO] Templates saved to: {output_file}")
    print()


def main():
    """Generate and display all cURL templates."""
    templates = generate_all_templates()

    # Optionally save to file
    save_choice = input("\nSave templates to file? (y/n): ").strip().lower()
    if save_choice == "y":
        save_templates_to_file(templates)

    print("\n[SUCCESS] Template generation complete!")
    print()
    print("Next steps:")
    print("  1. Test each cURL command during a live game")
    print("  2. Find the one that returns boxscore data")
    print("  3. Update ENDPOINT_PATH in test_lnb_boxscore_discovery.py")
    print("  4. Run test_lnb_boxscore_discovery.py to validate")
    print()


if __name__ == "__main__":
    main()
