#!/usr/bin/env python3
"""NBL/NZ-NBL Setup Verification Script

This script checks that:
1. R is installed and accessible
2. Required R packages (nblR, arrow, dplyr) are installed
3. NBL data has been exported from R
4. Data can be loaded and queried via Python
5. All expected datasets are available

Run this after completing the setup guide to verify everything works.

Usage:
    python verify_nbl_setup.py
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple


def check_r_installed() -> Tuple[bool, str]:
    """Check if R is installed and accessible"""
    try:
        result = subprocess.run(
            ["R", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split("\n")[0]
            return True, f"✅ R is installed: {version}"
        else:
            return False, "❌ R found but returned error"
    except FileNotFoundError:
        return False, "❌ R not found in PATH. Install R first."
    except Exception as e:
        return False, f"❌ Error checking R: {e}"


def check_r_packages() -> Tuple[bool, str]:
    """Check if required R packages are installed"""
    packages = ["nblR", "arrow", "dplyr"]
    try:
        cmd = f'library({packages[0]}); library({packages[1]}); library({packages[2]})'
        result = subprocess.run(
            ["R", "-e", cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, f"✅ R packages installed: {', '.join(packages)}"
        else:
            missing = []
            for pkg in packages:
                if pkg in result.stderr:
                    missing.append(pkg)
            if missing:
                return False, f"❌ Missing R packages: {', '.join(missing)}\n   Install: R -e 'install.packages(c(\"nblR\",\"arrow\",\"dplyr\"))'"
            return False, "❌ R packages check failed"
    except Exception as e:
        return False, f"❌ Error checking R packages: {e}"


def check_export_script() -> Tuple[bool, str]:
    """Check if export script exists"""
    script_path = Path("tools/nbl/export_nbl.R")
    if script_path.exists():
        return True, f"✅ Export script found: {script_path}"
    else:
        return False, f"❌ Export script not found: {script_path}"


def check_parquet_files() -> Tuple[bool, str]:
    """Check if Parquet files have been exported"""
    export_dir = Path("data/nbl_raw")
    expected_files = [
        "nbl_results.parquet",
        "nbl_box_player.parquet",
        "nbl_box_team.parquet",
        "nbl_pbp.parquet",
        "nbl_shots.parquet",
    ]

    if not export_dir.exists():
        return False, f"❌ Export directory not found: {export_dir}\n   Run: Rscript tools/nbl/export_nbl.R"

    found = []
    missing = []
    for fname in expected_files:
        path = export_dir / fname
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            found.append(f"{fname} ({size_mb:.1f} MB)")
        else:
            missing.append(fname)

    if missing:
        return False, f"❌ Missing Parquet files: {', '.join(missing)}\n   Run: Rscript tools/nbl/export_nbl.R"

    return True, f"✅ All Parquet files found:\n   " + "\n   ".join(found)


def check_python_imports() -> Tuple[bool, str]:
    """Check if Python modules can be imported"""
    try:
        from cbb_data.fetchers import nbl_official
        from cbb_data.api.datasets import get_dataset
        return True, "✅ Python modules imported successfully"
    except ImportError as e:
        return False, f"❌ Import error: {e}"


def check_data_loading() -> Tuple[bool, str]:
    """Check if NBL data can be loaded"""
    try:
        from cbb_data.fetchers.nbl_official import load_nbl_table

        # Try loading results (smallest file)
        df = load_nbl_table("nbl_results")
        if df.empty:
            return False, "❌ NBL results loaded but empty"

        return True, f"✅ NBL data loads successfully ({len(df)} games found)"
    except FileNotFoundError:
        return False, "❌ NBL data not yet exported\n   Run: Rscript tools/nbl/export_nbl.R"
    except Exception as e:
        return False, f"❌ Error loading NBL data: {e}"


def check_dataset_access() -> Tuple[bool, str]:
    """Check if NBL datasets are accessible via high-level API"""
    try:
        from cbb_data.api.datasets import get_dataset

        # Try fetching schedule
        schedule = get_dataset("games", filters={"league": "NBL", "season": "2023"})
        if schedule.empty:
            return False, "⚠️  NBL schedule accessible but empty (may need data for 2023 season)"

        return True, f"✅ NBL datasets accessible via API ({len(schedule)} games for 2023)"
    except Exception as e:
        return False, f"❌ Error accessing NBL datasets: {e}"


def check_shot_coordinates() -> Tuple[bool, str]:
    """Check if shot coordinates are available (the premium feature!)"""
    try:
        from cbb_data.fetchers.nbl_official import load_nbl_table

        shots = load_nbl_table("nbl_shots")
        if shots.empty:
            return False, "⚠️  No shot data found"

        # Check for coordinates
        if "loc_x" in shots.columns and "loc_y" in shots.columns:
            non_null = shots["loc_x"].notna().sum()
            total = len(shots)
            pct = (non_null / total * 100) if total > 0 else 0
            return True, f"✅ Shot coordinates available! ({non_null:,} shots, {pct:.1f}% with x,y)"
        else:
            return False, "❌ Shot coordinate columns not found"
    except Exception as e:
        return False, f"❌ Error checking shot coordinates: {e}"


def main():
    """Run all verification checks"""
    print("=" * 70)
    print("NBL/NZ-NBL Setup Verification")
    print("=" * 70)
    print()

    checks = [
        ("R Installation", check_r_installed),
        ("R Packages", check_r_packages),
        ("Export Script", check_export_script),
        ("Parquet Files", check_parquet_files),
        ("Python Imports", check_python_imports),
        ("Data Loading", check_data_loading),
        ("Dataset Access", check_dataset_access),
        ("Shot Coordinates", check_shot_coordinates),
    ]

    results = []
    for name, check_func in checks:
        print(f"Checking {name}...", end=" ", flush=True)
        success, message = check_func()
        results.append((name, success, message))
        print()
        print(f"  {message}")
        print()

    # Summary
    print("=" * 70)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    if passed == total:
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print()
        print("Your NBL/NZ-NBL setup is complete and working!")
        print()
        print("Next steps:")
        print("  1. Run health tests: pytest tests/test_nbl_official_consistency.py")
        print("  2. Query data: python -c \"from cbb_data.api.datasets import get_dataset; print(get_dataset('shots', filters={'league': 'NBL'}).head())\"")
        print("  3. Build shot charts and advanced metrics!")
        return 0
    else:
        print(f"⚠️  {passed}/{total} CHECKS PASSED")
        print()
        print("Failed checks:")
        for name, success, message in results:
            if not success:
                print(f"  - {name}")
        print()
        print("See messages above for details on how to fix.")
        print("Consult tools/nbl/SETUP_GUIDE.md for complete setup instructions.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
