#!/usr/bin/env python3
"""NBL R Setup Validation Script

This script validates that the R environment is properly configured for NBL data export.

Usage:
    python tools/nbl/validate_setup.py

Checks:
    1. R installation (Rscript available)
    2. Required R packages (nblR, dplyr, arrow)
    3. Export script exists
    4. Python dependencies (pandas, pyarrow, duckdb)
    5. Directory structure (data/nbl_raw)
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def check_r_installation() -> bool:
    """Check if R and Rscript are installed"""
    logger.info("=" * 70)
    logger.info("1. Checking R Installation")
    logger.info("=" * 70)

    try:
        result = subprocess.run(
            ["Rscript", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        version = result.stderr.strip() if result.stderr else result.stdout.strip()
        logger.info(f"✅ R is installed: {version}")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ R is NOT installed or not in PATH")
        logger.error("")
        logger.error("Install R:")
        logger.error("  • Windows: https://cran.r-project.org/bin/windows/base/")
        logger.error("  • macOS: brew install r")
        logger.error("  • Ubuntu/Debian: sudo apt-get install r-base")
        logger.error("")
        return False


def check_r_packages() -> tuple[bool, list[str]]:
    """Check if required R packages are installed"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("2. Checking R Package Dependencies")
    logger.info("=" * 70)

    required_packages = ["nblR", "dplyr", "arrow"]
    missing_packages = []

    for package in required_packages:
        try:
            # Check if package is installed
            # Use --vanilla to avoid startup file issues on Windows
            r_code = f'if (!requireNamespace("{package}", quietly = TRUE)) quit(status = 1)'
            subprocess.run(
                ["Rscript", "--vanilla", "-e", r_code],
                capture_output=True,
                check=True,
            )
            logger.info(f"✅ R package '{package}' is installed")

        except subprocess.CalledProcessError:
            logger.error(f"❌ R package '{package}' is NOT installed")
            missing_packages.append(package)

    if missing_packages:
        logger.error("")
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.error("")
        logger.error("Install with (recommended):")
        logger.error("  Rscript tools/nbl/install_nbl_packages.R")
        logger.error("")
        logger.error("OR manually in R console:")
        logger.error("  1. Run: R")
        packages_str = '", "'.join(missing_packages)
        logger.error(
            f'  2. Then: install.packages(c("{packages_str}"), '
            'repos="https://cloud.r-project.org")'
        )
        logger.error("")
        return False, missing_packages

    return True, []


def check_export_script() -> bool:
    """Check if the R export script exists"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("3. Checking Export Script")
    logger.info("=" * 70)

    script_path = Path("tools/nbl/export_nbl.R")

    if script_path.exists():
        logger.info(f"✅ Export script found: {script_path}")
        logger.info(f"   Size: {script_path.stat().st_size:,} bytes")
        return True
    else:
        logger.error(f"❌ Export script NOT found: {script_path}")
        logger.error("")
        logger.error("This script should be in the repository.")
        logger.error("Check that you're running from the project root directory.")
        logger.error("")
        return False


def check_python_dependencies() -> tuple[bool, list[str]]:
    """Check if required Python packages are installed"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("4. Checking Python Dependencies")
    logger.info("=" * 70)

    required_packages = {
        "pandas": "pandas",
        "pyarrow": "pyarrow",
        "duckdb": "duckdb",
    }

    missing_packages = []

    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            logger.info(f"✅ Python package '{package_name}' is installed")
        except ImportError:
            logger.error(f"❌ Python package '{package_name}' is NOT installed")
            missing_packages.append(package_name)

    if missing_packages:
        logger.error("")
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.error("")
        logger.error("Install with:")
        logger.error(f"  uv pip install {' '.join(missing_packages)}")
        logger.error("")
        return False, missing_packages

    return True, []


def check_directory_structure() -> bool:
    """Check if required directories exist"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("5. Checking Directory Structure")
    logger.info("=" * 70)

    export_dir = Path("data/nbl_raw")

    if export_dir.exists():
        logger.info(f"✅ Export directory exists: {export_dir}")

        # Check for existing Parquet files
        parquet_files = list(export_dir.glob("*.parquet"))
        if parquet_files:
            logger.info(f"   Found {len(parquet_files)} existing Parquet file(s):")
            for pf in sorted(parquet_files):
                size_mb = pf.stat().st_size / (1024 * 1024)
                logger.info(f"     • {pf.name} ({size_mb:.2f} MB)")
        else:
            logger.info("   (No Parquet files found - run export to populate)")
    else:
        logger.info(f"ℹ️  Export directory will be created: {export_dir}")
        logger.info("   (This is normal for first-time setup)")

    return True


def main() -> int:
    """Run all validation checks"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 17 + "NBL R Setup Validation" + " " * 29 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")

    checks = [
        ("R Installation", check_r_installation),
        ("R Packages", lambda: check_r_packages()[0]),
        ("Export Script", check_export_script),
        ("Python Dependencies", lambda: check_python_dependencies()[0]),
        ("Directory Structure", check_directory_structure),
    ]

    results = []
    for name, check_func in checks:
        try:
            results.append(check_func())
        except Exception as e:
            logger.error(f"❌ Unexpected error during '{name}' check: {e}")
            results.append(False)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("Summary")
    logger.info("=" * 70)

    passed = sum(results)
    total = len(results)

    for i, (name, _) in enumerate(checks):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        logger.info(f"{status}  {name}")

    logger.info("")
    logger.info(f"Result: {passed}/{total} checks passed")
    logger.info("")

    if all(results):
        logger.info("🎉 All checks passed! You're ready to run NBL data export.")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Export NBL data: Rscript tools/nbl/export_nbl.R")
        logger.info("  2. Or use Python CLI: uv run nbl-export")
        logger.info("")
        logger.info("Documentation: tools/nbl/SETUP_GUIDE.md")
        logger.info("")
        return 0
    else:
        logger.error("⚠️  Some checks failed. Please fix the issues above.")
        logger.error("")
        logger.error("For detailed setup instructions, see:")
        logger.error("  tools/nbl/SETUP_GUIDE.md")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
