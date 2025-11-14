#!/usr/bin/env python3
"""
Complete Validation Pipeline for International Basketball Leagues

This script runs the full validation workflow:
1. Quick structure validation
2. Import validation
3. Game index validation (if available)
4. Data fetching tests (if game indexes are valid)
5. Comprehensive reporting

Usage:
    python tools/run_complete_validation.py               # All leagues
    python tools/run_complete_validation.py BCL           # Single league
    python tools/run_complete_validation.py BCL BAL ABA   # Multiple leagues
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List


class Colors:
    """ANSI color codes"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


class ValidationPipeline:
    """Complete validation pipeline runner"""

    def __init__(self, leagues: List[str]):
        self.leagues = leagues
        self.results_dir = Path(f"validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results = {}

    def print_header(self, title: str):
        """Print section header"""
        print("\n" + "=" * 70)
        print(title)
        print("=" * 70 + "\n")

    def run_command(self, cmd: List[str], log_file: Path, step_name: str) -> int:
        """Run a command and log output"""
        print(f"Running: {' '.join(cmd)}")

        with open(log_file, 'w') as f:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Write to log file
            f.write(result.stdout)

            # Also print to console
            print(result.stdout)

        return result.returncode

    def step_1_quick_validation(self):
        """Step 1: Quick structure validation"""
        self.print_header("STEP 1: Quick Structure Validation (no imports)")

        cmd = [
            "python", "tools/quick_validate_leagues.py",
            "--export", str(self.results_dir / "quick_validation.json")
        ]

        exit_code = self.run_command(
            cmd,
            self.results_dir / "01_quick_validation.log",
            "quick_validation"
        )

        if exit_code == 0:
            print(f"{Colors.GREEN}✅ Quick validation passed{Colors.NC}")
            self.results["quick_validation"] = "PASSED"
        else:
            print(f"{Colors.YELLOW}⚠️  Quick validation found issues{Colors.NC}")
            self.results["quick_validation"] = "WARNINGS"

        return exit_code

    def step_2_import_validation(self):
        """Step 2: Import validation"""
        self.print_header("STEP 2: Import Validation (test all modules load)")

        cmd = [
            "python", "tools/validate_international_data.py",
            "--quick",
            "--export", str(self.results_dir / "import_validation.json")
        ]

        exit_code = self.run_command(
            cmd,
            self.results_dir / "02_import_validation.log",
            "import_validation"
        )

        if exit_code != 0:
            print(f"{Colors.RED}❌ Import validation failed - cannot proceed{Colors.NC}")
            print(f"See {self.results_dir / '02_import_validation.log'} for details")
            self.results["import_validation"] = "FAILED"
            return exit_code

        print(f"{Colors.GREEN}✅ All imports successful{Colors.NC}")
        self.results["import_validation"] = "PASSED"
        return exit_code

    def step_3_game_index_validation(self):
        """Step 3: Game index validation (FIBA leagues only)"""
        self.print_header("STEP 3: Game Index Validation (FIBA leagues)")

        fiba_leagues = [l for l in self.leagues if l in ["BCL", "BAL", "ABA", "LKL"]]
        self.results["game_index_validation"] = {}

        for league in fiba_leagues:
            print(f"Validating {league} game index...")

            cmd = [
                "python", "tools/fiba_game_index_validator.py",
                "--league", league,
                "--season", "2023-24",
                "--report"
            ]

            log_file = self.results_dir / f"03_game_index_{league}.log"

            exit_code = self.run_command(cmd, log_file, f"game_index_{league}")

            # Check if index is ready
            with open(log_file, 'r') as f:
                log_content = f.read()

            if "Index ready for use" in log_content:
                print(f"{Colors.GREEN}✅ {league} game index valid{Colors.NC}")
                self.results["game_index_validation"][league] = "VALID"
            else:
                print(f"{Colors.YELLOW}⚠️  {league} game index has issues{Colors.NC}")
                self.results["game_index_validation"][league] = "ISSUES"

    def step_4_flow_testing(self):
        """Step 4: Complete flow testing (per league)"""
        self.print_header("STEP 4: Complete Flow Testing (data fetching)")

        print("NOTE: This step requires valid game indexes and network access")
        print("Skipping for now (run manually when ready)")
        print()

        # Uncomment when game indexes have real data:
        # for league in self.leagues:
        #     print(f"Testing {league} complete flow...")
        #
        #     cmd = [
        #         "python", "tools/test_league_complete_flow.py",
        #         "--league", league,
        #         "--season", "2023-24",
        #         "--quick",
        #         "--export", str(self.results_dir / f"04_flow_test_{league}.json")
        #     ]
        #
        #     exit_code = self.run_command(
        #         cmd,
        #         self.results_dir / f"04_flow_test_{league}.log",
        #         f"flow_test_{league}"
        #     )

    def step_5_comprehensive_validation(self):
        """Step 5: Comprehensive validation"""
        self.print_header("STEP 5: Comprehensive Validation (full test suite)")

        if self.results.get("import_validation") != "PASSED":
            print(f"{Colors.YELLOW}⚠️  Skipping (imports failed){Colors.NC}")
            return

        cmd = [
            "python", "tools/validate_international_data.py",
            "--comprehensive",
            "--export", str(self.results_dir / "05_comprehensive_validation.json")
        ]

        exit_code = self.run_command(
            cmd,
            self.results_dir / "05_comprehensive_validation.log",
            "comprehensive_validation"
        )

        if exit_code == 0:
            print(f"{Colors.GREEN}✅ Comprehensive validation passed{Colors.NC}")
            self.results["comprehensive_validation"] = "PASSED"
        else:
            print(f"{Colors.YELLOW}⚠️  Comprehensive validation found issues{Colors.NC}")
            self.results["comprehensive_validation"] = "WARNINGS"

    def step_6_generate_summary(self):
        """Step 6: Generate summary report"""
        self.print_header("STEP 6: Generating Summary Report")

        summary_file = self.results_dir / "SUMMARY.md"

        with open(summary_file, 'w') as f:
            f.write(f"# Validation Summary\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Leagues Tested**: {', '.join(self.leagues)}\n")
            f.write(f"**Results Directory**: {self.results_dir}\n\n")
            f.write(f"---\n\n")

            # Quick validation
            f.write(f"## Quick Validation\n\n")
            status = self.results.get("quick_validation", "UNKNOWN")
            if status == "PASSED":
                f.write("✅ **PASSED** - All code structure checks passed\n\n")
            else:
                f.write("⚠️  **WARNINGS** - See `01_quick_validation.log`\n\n")

            f.write(f"---\n\n")

            # Import validation
            f.write(f"## Import Validation\n\n")
            status = self.results.get("import_validation", "UNKNOWN")
            if status == "PASSED":
                f.write("✅ **PASSED** - All modules import successfully\n\n")
            else:
                f.write("❌ **FAILED** - Import errors found\n\n")

            f.write(f"---\n\n")

            # Game index validation
            f.write(f"## Game Index Validation\n\n")
            f.write(f"| League | Status | Details |\n")
            f.write(f"|--------|--------|--------|\n")

            for league in self.leagues:
                if league in ["BCL", "BAL", "ABA", "LKL"]:
                    status = self.results.get("game_index_validation", {}).get(league, "UNKNOWN")
                    if status == "VALID":
                        f.write(f"| {league} | ✅ Valid | Ready for use |\n")
                    else:
                        f.write(f"| {league} | ⚠️  Issues | See log file |\n")
                else:
                    f.write(f"| {league} | N/A | Not FIBA league |\n")

            f.write(f"\n---\n\n")

            # Next steps
            f.write(f"## Next Steps\n\n")
            f.write(f"### If All Validations Passed ✅\n\n")
            f.write(f"1. **Collect Real Game IDs**:\n")
            f.write(f"   ```bash\n")
            f.write(f"   python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive\n")
            f.write(f"   ```\n\n")
            f.write(f"2. **Test Complete Data Flow**:\n")
            f.write(f"   ```bash\n")
            f.write(f"   python tools/test_league_complete_flow.py --league BCL --season 2023-24\n")
            f.write(f"   ```\n\n")

            f.write(f"### If Validations Failed ❌\n\n")
            f.write(f"1. Check logs in `{self.results_dir}`\n")
            f.write(f"2. Fix identified issues\n")
            f.write(f"3. Re-run validation\n\n")

            f.write(f"---\n\n")

            # Files generated
            f.write(f"## Files Generated\n\n")
            for file_path in sorted(self.results_dir.iterdir()):
                if file_path.is_file():
                    size = file_path.stat().st_size / 1024  # KB
                    f.write(f"- `{file_path.name}` ({size:.1f} KB)\n")

            f.write(f"\n---\n\n")

            # Reference documentation
            f.write(f"## Reference Documentation\n\n")
            f.write(f"- **Testing Guide**: docs/TESTING_VALIDATION_GUIDE.md\n")
            f.write(f"- **Changes Summary**: docs/SESSION_CHANGES_SUMMARY.md\n")
            f.write(f"- **Validation Details**: VALIDATION_SUMMARY.md\n")
            f.write(f"- **League Examples**: docs/INTERNATIONAL_LEAGUES_EXAMPLES.md\n")

        print(f"{Colors.GREEN}✅ Summary report generated: {summary_file}{Colors.NC}")

        # Display summary
        self.print_header("VALIDATION PIPELINE COMPLETE")
        with open(summary_file, 'r') as f:
            print(f.read())

        print(f"\n{'='*70}")
        print(f"Full results saved to: {self.results_dir}")
        print(f"{'='*70}\n")

    def run(self):
        """Run complete validation pipeline"""
        print("=" * 70)
        print("INTERNATIONAL BASKETBALL LEAGUES - COMPLETE VALIDATION PIPELINE")
        print("=" * 70)
        print(f"Leagues: {', '.join(self.leagues)}")
        print(f"Results: {self.results_dir}")
        print("=" * 70)

        # Run all steps
        self.step_1_quick_validation()
        import_exit_code = self.step_2_import_validation()

        if import_exit_code != 0:
            print(f"\n{Colors.RED}❌ Import validation failed - stopping pipeline{Colors.NC}\n")
            self.step_6_generate_summary()
            return 1

        self.step_3_game_index_validation()
        self.step_4_flow_testing()
        self.step_5_comprehensive_validation()
        self.step_6_generate_summary()

        return 0


def main():
    """Main validation workflow"""
    parser = argparse.ArgumentParser(
        description="Complete validation pipeline for international basketball leagues"
    )
    parser.add_argument(
        "leagues",
        nargs="*",
        default=["BCL", "BAL", "ABA", "LKL", "ACB", "LNB"],
        help="Leagues to validate (default: all)"
    )

    args = parser.parse_args()

    # Run pipeline
    pipeline = ValidationPipeline(args.leagues)
    exit_code = pipeline.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
