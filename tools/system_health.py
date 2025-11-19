"""System Health Check

Quick environment verification for cbb_data package.
Reports availability of core and optional dependencies.

Usage:
    python tools/system_health.py

Output:
    One-line summary of environment status, plus detailed breakdown.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def check_core_dependencies() -> dict[str, bool]:
    """Check core required dependencies"""
    results = {}

    # Core packages
    core_packages = [
        ("pandas", "pandas"),
        ("requests", "requests"),
        ("beautifulsoup4", "bs4"),
        ("duckdb", "duckdb"),
        ("pyarrow", "pyarrow"),
    ]

    for name, import_name in core_packages:
        try:
            __import__(import_name)
            results[name] = True
        except ImportError:
            results[name] = False

    return results


def check_optional_dependencies() -> dict[str, tuple[bool, str]]:
    """Check optional dependencies with status messages

    Returns:
        Dict mapping dependency name to (available, status_message)
    """
    import importlib.util

    results = {}

    # Playwright (for NZ-NBL)
    if importlib.util.find_spec("playwright") is not None:
        results["playwright"] = (True, "Available")
    else:
        results["playwright"] = (
            False,
            "Not installed - install with: uv sync --extra nz_nbl && playwright install chromium",
        )

    # rpy2 (for ACB BAwiR)
    try:
        from rpy2.robjects import pandas2ri

        pandas2ri.activate()
        results["rpy2"] = (True, "Available and connected to R")
    except ImportError:
        results["rpy2"] = (False, "Not installed - install with: uv sync --extra acb")
    except TypeError:
        # Windows-specific: R not built as shared library
        results["rpy2"] = (False, "Windows R shared library issue - use WSL or devcontainer")
    except OSError as e:
        results["rpy2"] = (False, f"R connection failed: {e}")
    except Exception as e:
        results["rpy2"] = (False, f"Initialization failed: {e}")

    # BAwiR R package (requires rpy2)
    if results.get("rpy2", (False,))[0]:
        try:
            from rpy2.robjects.packages import importr

            importr("BAwiR")  # Just verify it loads
            results["BAwiR"] = (True, "R package loaded")
        except Exception:
            results["BAwiR"] = (False, "R package not installed: install.packages('BAwiR')")
    else:
        results["BAwiR"] = (False, "Requires rpy2")

    # cbbpy (for NCAA data)
    if importlib.util.find_spec("cbbpy") is not None:
        results["cbbpy"] = (True, "Available")
    else:
        results["cbbpy"] = (False, "Not installed - install with: uv pip install cbbpy")

    return results


def check_r_installation() -> tuple[bool, str]:
    """Check if R is installed and accessible"""
    import subprocess

    try:
        result = subprocess.run(["Rscript", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stderr.strip() or result.stdout.strip()
            return True, version
        else:
            return False, "Rscript command failed"
    except FileNotFoundError:
        return False, "R/Rscript not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "Rscript timed out"
    except Exception as e:
        return False, f"Error checking R: {e}"


def main():
    """Run system health check and print summary"""
    print("=" * 60)
    print("SYSTEM HEALTH CHECK - cbb_data environment")
    print("=" * 60)
    print()

    # Core dependencies
    print("Core Dependencies:")
    print("-" * 40)
    core = check_core_dependencies()
    core_ok = all(core.values())

    for name, available in core.items():
        status = "OK" if available else "MISSING"
        symbol = "+" if available else "X"
        print(f"  [{symbol}] {name}: {status}")

    print()

    # R installation
    print("R Installation:")
    print("-" * 40)
    r_available, r_status = check_r_installation()
    r_symbol = "+" if r_available else "X"
    print(f"  [{r_symbol}] R: {r_status}")
    print()

    # Optional dependencies
    print("Optional Dependencies:")
    print("-" * 40)
    optional = check_optional_dependencies()

    for name, (available, message) in optional.items():
        symbol = "+" if available else "-"
        print(f"  [{symbol}] {name}: {message}")

    print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    optional_available = sum(1 for avail, _ in optional.values() if avail)
    optional_total = len(optional)

    if not core_ok:
        missing = [k for k, v in core.items() if not v]
        print(f"CRITICAL: Missing core dependencies: {', '.join(missing)}")
        print("Run: uv sync")
        return 1

    # Build one-line summary
    features = []
    if optional.get("playwright", (False,))[0]:
        features.append("NZ-NBL")
    if optional.get("BAwiR", (False,))[0]:
        features.append("ACB-BAwiR")
    elif optional.get("rpy2", (False,))[0]:
        features.append("rpy2")
    if optional.get("cbbpy", (False,))[0]:
        features.append("NCAA")

    core_status = "Core OK"
    optional_status = f"{optional_available}/{optional_total} optional"
    feature_str = f" ({', '.join(features)})" if features else ""

    print(f"{core_status}, {optional_status}{feature_str}")
    print()

    # Recommendations
    if optional_available < optional_total:
        print("To enable all features:")
        if not optional.get("playwright", (False,))[0]:
            print("  - NZ-NBL: uv sync --extra nz_nbl && playwright install chromium")
        if not optional.get("rpy2", (False,))[0]:
            print("  - ACB BAwiR: uv sync --extra acb (+ R shared library on Windows)")
        elif not optional.get("BAwiR", (False,))[0]:
            print("  - BAwiR: Rscript -e \"install.packages('BAwiR')\"")
        if not optional.get("cbbpy", (False,))[0]:
            print("  - NCAA: uv pip install cbbpy")
        print()
        print("Note: On Windows, rpy2 requires R built with --enable-R-shlib.")
        print("      Consider using WSL or devcontainer for full BAwiR support.")
    else:
        print("All features available!")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
