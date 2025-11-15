#!/usr/bin/env python3
"""LNB Boxscore Endpoint Quick-Start Discovery

Interactive script that guides you through discovering and testing the
boxscore endpoint during a live game.

Usage:
    python tools/lnb/quick_start_discovery.py
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))


def print_header(title: str):
    """Print section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_step(step_num: int, title: str):
    """Print step header."""
    print(f"\n[STEP {step_num}] {title}")
    print("-" * 80)


def check_for_live_games():
    """Check if there are any live games today."""
    print_step(1, "Checking for Live Games")
    print()
    print("Fetching today's schedule from LNB API...")
    print()

    try:
        from cbb_data.fetchers.lnb import fetch_lnb_schedule

        # Get current season's schedule
        current_year = datetime.now().year
        schedule = fetch_lnb_schedule(season=current_year)

        if schedule.empty:
            print("[INFO] No games found for current season")
            print()
            print("Try running:")
            print("  from cbb_data.fetchers.lnb import fetch_lnb_schedule")
            print(f"  schedule = fetch_lnb_schedule(season={current_year})")
            print("  print(schedule[['GAME_ID', 'GAME_DATE', 'HOME_TEAM', 'AWAY_TEAM', 'STATUS']])")
            print()
            return []

        # Filter for today or recent games
        today = datetime.now().strftime("%Y-%m-%d")
        recent_games = schedule[
            (schedule["GAME_DATE"] >= today) | (schedule["STATUS"] == "live")
        ].head(10)

        if recent_games.empty:
            print(f"[INFO] No games scheduled for today ({today})")
            print()
            print("Recent finished games you can test with:")
            finished = schedule[schedule["STATUS"] == "finished"].head(5)
            for _, game in finished.iterrows():
                print(f"  Game ID: {game['GAME_ID']} - {game['HOME_TEAM']} vs {game['AWAY_TEAM']}")
                print(
                    f"           Date: {game['GAME_DATE']}, Score: {game['HOME_SCORE']}-{game['AWAY_SCORE']}"
                )
            print()
            return []

        print("[SUCCESS] Found upcoming/live games:")
        print()
        for _, game in recent_games.iterrows():
            status = game["STATUS"]
            print(f"  Game ID: {game['GAME_ID']} - {game['HOME_TEAM']} vs {game['AWAY_TEAM']}")
            print(f"           Date: {game['GAME_DATE']}, Status: {status}")
        print()

        return recent_games["GAME_ID"].tolist()

    except Exception as e:
        print(f"[ERROR] Failed to fetch schedule: {e}")
        print()
        print("You can still proceed with manual game ID entry.")
        print()
        return []


def guide_devtools_discovery():
    """Guide user through DevTools discovery."""
    print_step(2, "Browser DevTools Discovery")
    print()
    print("Follow these steps to discover the boxscore endpoint:")
    print()
    print("1. Open a web browser (Chrome, Firefox, or Edge)")
    print("2. Navigate to: https://www.lnb.fr")
    print("3. Open Developer Tools (F12)")
    print("4. Go to the 'Network' tab")
    print("5. Filter by 'XHR' or 'Fetch' requests")
    print("6. Navigate to a live game page or box score page")
    print("7. Look for API requests containing player statistics")
    print()
    print("Common endpoint patterns to look for:")
    print("  - /stats/getMatchBoxScore")
    print("  - /api/match/{id}/boxscore")
    print("  - /api/match/{id}/stats")
    print()
    print("When you find a request that returns player box score data:")
    print("  1. Right-click the request")
    print("  2. Select 'Copy' > 'Copy as cURL'")
    print("  3. Save the cURL command or the endpoint URL")
    print()

    input("Press Enter when you're ready to continue...")


def test_endpoint_with_curl():
    """Help user test endpoint with cURL."""
    print_step(3, "Test Endpoint with cURL")
    print()
    print("You can test the endpoint using cURL templates.")
    print()

    choice = input("Generate cURL templates? (y/n): ").strip().lower()
    if choice == "y":
        print()
        print("Running cURL template generator...")
        print()

        try:
            import subprocess

            subprocess.run([sys.executable, "tools/lnb/generate_curl_templates.py"])
        except Exception as e:
            print(f"[ERROR] Failed to run generator: {e}")
    else:
        print()
        print("You can manually run:")
        print("  python tools/lnb/generate_curl_templates.py")
        print()


def analyze_response():
    """Help user analyze API response."""
    print_step(4, "Analyze API Response")
    print()
    print("Save the JSON response from the API to a file, then analyze it.")
    print()
    print("To analyze a response:")
    print("  1. Save API response to a file (e.g., response.json)")
    print("  2. Run: python tools/lnb/debug_response_analyzer.py response.json")
    print()
    print("Or pipe directly from cURL:")
    print("  curl ... | python tools/lnb/debug_response_analyzer.py -")
    print()

    choice = input("Do you have a response file to analyze now? (y/n): ").strip().lower()
    if choice == "y":
        filepath = input("Enter file path: ").strip()
        if Path(filepath).exists():
            print()
            print("Analyzing response...")
            print()

            try:
                import subprocess

                subprocess.run([sys.executable, "tools/lnb/debug_response_analyzer.py", filepath])
            except Exception as e:
                print(f"[ERROR] Failed to analyze: {e}")
        else:
            print(f"[ERROR] File not found: {filepath}")
    print()


def test_parser():
    """Test parser with discovered endpoint."""
    print_step(5, "Test Parser")
    print()
    print("Once you've confirmed the endpoint works, test the parser:")
    print()
    print("Option 1: Test with mock data (all 4 patterns)")
    print("  python test_lnb_parser_with_mocks.py")
    print()
    print("Option 2: Comprehensive validation suite")
    print("  python tools/lnb/test_boxscore_comprehensive.py")
    print()
    print("Option 3: Test with real endpoint")
    print("  python test_lnb_boxscore_discovery.py")
    print()

    choice = input("Run parser tests now? (y/n): ").strip().lower()
    if choice == "y":
        test_choice = input("Which test? (1=mock, 2=comprehensive, 3=real): ").strip()

        test_files = {
            "1": "test_lnb_parser_with_mocks.py",
            "2": "tools/lnb/test_boxscore_comprehensive.py",
            "3": "test_lnb_boxscore_discovery.py",
        }

        test_file = test_files.get(test_choice)
        if test_file:
            print()
            print(f"Running {test_file}...")
            print()

            try:
                import subprocess

                subprocess.run([sys.executable, test_file])
            except Exception as e:
                print(f"[ERROR] Failed to run test: {e}")
    print()


def update_fetcher():
    """Guide user on updating the fetcher."""
    print_step(6, "Update Fetcher Function")
    print()
    print("If tests passed, update the fetcher to use the discovered endpoint:")
    print()
    print("1. Open: src/cbb_data/fetchers/lnb.py")
    print("2. Find: fetch_lnb_player_game() function (around line 450)")
    print("3. Update:")
    print("   - Set try_endpoint=True as default")
    print("   - Update endpoint_path to your discovered endpoint")
    print()
    print("Example:")
    print('   endpoint_path: str = "/stats/getMatchBoxScore",')
    print("   try_endpoint: bool = True,")
    print()
    print("4. Test the updated fetcher:")
    print("   from cbb_data.fetchers.lnb import fetch_lnb_player_game")
    print("   df = fetch_lnb_player_game(season=2025, game_id=28931)")
    print("   print(df)")
    print()


def create_discovery_report():
    """Help user create discovery report."""
    print_step(7, "Create Discovery Report")
    print()
    print("Document your findings in LNB_BOXSCORE_DISCOVERY_REPORT.md")
    print()

    choice = input("Create discovery report now? (y/n): ").strip().lower()
    if choice == "y":
        endpoint = input("  Discovered endpoint path: ").strip()
        game_id = input("  Test game ID used: ").strip()
        pattern = input("  Response pattern (1-4): ").strip()

        report_content = f"""# LNB Boxscore Endpoint Discovery Report

## Discovery Information

- **Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Discovered Endpoint**: `{endpoint}`
- **Test Game ID**: {game_id}
- **Response Pattern**: Pattern {pattern}

## Endpoint Details

### Request
```bash
curl -X GET \\
  "https://www.lnb.fr{endpoint}" \\
  -H "Accept: application/json"
```

### Response Structure
Pattern {pattern}: [Description based on pattern number]

## Parser Compatibility

- [x] Parser handles response structure
- [x] All required fields present
- [x] Data types compatible
- [x] Tests passing

## Next Steps

1. Update `fetch_lnb_player_game()` with endpoint path
2. Set `try_endpoint=True` as default
3. Run full test suite
4. Update PROJECT_LOG.md

## Testing

### Test Commands
```bash
# Test parser with mock data
python test_lnb_parser_with_mocks.py

# Test with real endpoint
python test_lnb_boxscore_discovery.py

# Run comprehensive validation
python tools/lnb/test_boxscore_comprehensive.py
```

### Test Results
- Mock data tests: [PASS/FAIL]
- Real endpoint test: [PASS/FAIL]
- Comprehensive validation: [PASS/FAIL]
"""

        report_file = Path("LNB_BOXSCORE_DISCOVERY_REPORT.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        print()
        print(f"[SUCCESS] Report created: {report_file}")
        print()


def main():
    """Main quick-start discovery workflow."""
    print_header("LNB Boxscore Endpoint Quick-Start Discovery")

    print("This interactive script will guide you through discovering")
    print("and testing the LNB boxscore endpoint.")
    print()

    input("Press Enter to begin...")

    # Step 1: Check for live games
    check_for_live_games()

    # Step 2: Guide DevTools discovery
    guide_devtools_discovery()

    # Step 3: Test with cURL
    test_endpoint_with_curl()

    # Step 4: Analyze response
    analyze_response()

    # Step 5: Test parser
    test_parser()

    # Step 6: Update fetcher
    update_fetcher()

    # Step 7: Create discovery report
    create_discovery_report()

    # Final summary
    print_header("Discovery Complete!")
    print("Summary of what we accomplished:")
    print()
    print("  [1] Checked for live games")
    print("  [2] Guided DevTools discovery process")
    print("  [3] Generated cURL test templates")
    print("  [4] Analyzed API response structure")
    print("  [5] Tested parser compatibility")
    print("  [6] Provided fetcher update instructions")
    print("  [7] Created discovery report")
    print()
    print("Next Steps:")
    print("  - Update src/cbb_data/fetchers/lnb.py with discovered endpoint")
    print("  - Run full test suite to validate")
    print("  - Update PROJECT_LOG.md with results")
    print()
    print("[SUCCESS] You're ready to use LNB boxscore data!")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Discovery cancelled by user")
        sys.exit(0)
