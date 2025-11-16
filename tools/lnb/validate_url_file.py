#!/usr/bin/env python3
"""Validate LNB match-center URL files before discovery

This script validates URL files to catch formatting errors before running
the UUID discovery process.

Checks performed:
- Valid UUID format in URLs
- No duplicate UUIDs
- Proper URL format
- Counts total valid URLs

Usage:
    # Validate a single file
    uv run python tools/lnb/validate_url_file.py tools/lnb/urls_2024_2025.txt

    # Validate all season files
    uv run python tools/lnb/validate_url_file.py tools/lnb/urls_*.txt

Output:
    - Validation report with errors and warnings
    - Summary statistics
    - Exit code 0 if valid, 1 if errors found
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# VALIDATION CONFIG
# ==============================================================================

# UUID regex pattern (36 characters: 8-4-4-4-12)
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

# Valid URL patterns for LNB match-center
VALID_URL_PATTERNS = [
    r"https://lnb\.fr/fr/match-center/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    r"https://lnb\.fr/fr/pre-match-center\?mid=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    r"https://www\.lnb\.fr/fr/match-center/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    r"https://www\.lnb\.fr/fr/pre-match-center\?mid=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
]


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def extract_uuid_from_line(line: str) -> str | None:
    """Extract UUID from a line

    Args:
        line: Line from URL file

    Returns:
        UUID if found, None otherwise
    """
    match = UUID_PATTERN.search(line)
    if match:
        return match.group(0).lower()
    return None


def validate_url_format(line: str) -> dict:
    """Validate URL format

    Args:
        line: URL line to validate

    Returns:
        Dict with validation results
    """
    result = {
        "valid": False,
        "url": line,
        "uuid": None,
        "error": None,
    }

    # Check if matches any valid pattern
    is_valid_format = False
    for pattern in VALID_URL_PATTERNS:
        if re.fullmatch(pattern, line, re.IGNORECASE):
            is_valid_format = True
            break

    if not is_valid_format:
        result["error"] = "URL does not match expected format"
        return result

    # Extract UUID
    uuid = extract_uuid_from_line(line)
    if not uuid:
        result["error"] = "Could not extract UUID from URL"
        return result

    result["valid"] = True
    result["uuid"] = uuid
    return result


def validate_file(file_path: Path) -> dict:
    """Validate a URL file

    Args:
        file_path: Path to URL file

    Returns:
        Dict with validation results
    """
    print(f"\n{'='*80}")
    print(f"  VALIDATING: {file_path.name}")
    print(f"{'='*80}\n")

    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return {
            "valid": False,
            "total_lines": 0,
            "valid_urls": 0,
            "invalid_urls": 0,
            "duplicates": 0,
            "errors": [f"File not found: {file_path}"],
        }

    # Read file
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[ERROR] Failed to read file: {e}")
        return {
            "valid": False,
            "total_lines": 0,
            "valid_urls": 0,
            "invalid_urls": 0,
            "duplicates": 0,
            "errors": [f"Failed to read file: {e}"],
        }

    # Parse and validate
    results = {
        "valid": True,
        "total_lines": len(lines),
        "comment_lines": 0,
        "blank_lines": 0,
        "valid_urls": 0,
        "invalid_urls": 0,
        "duplicates": 0,
        "errors": [],
        "warnings": [],
        "uuids": [],
    }

    seen_uuids = set()
    line_number = 0

    for line in lines:
        line_number += 1
        stripped = line.strip()

        # Skip comments and blank lines
        if not stripped or stripped.startswith("#"):
            if not stripped:
                results["blank_lines"] += 1
            else:
                results["comment_lines"] += 1
            continue

        # Validate URL
        validation = validate_url_format(stripped)

        if validation["valid"]:
            uuid = validation["uuid"]

            # Check for duplicates
            if uuid in seen_uuids:
                results["duplicates"] += 1
                results["warnings"].append(
                    f"Line {line_number}: Duplicate UUID {uuid} (already seen earlier in file)"
                )
            else:
                seen_uuids.add(uuid)
                results["uuids"].append(uuid)
                results["valid_urls"] += 1

            print(f"  ✅ Line {line_number:3d}: {uuid}")

        else:
            results["invalid_urls"] += 1
            results["errors"].append(
                f"Line {line_number}: {validation['error']} - {stripped[:60]}..."
            )
            print(f"  ❌ Line {line_number:3d}: {validation['error']}")
            print(f"           {stripped[:60]}...")

    # Print summary
    print(f"\n{'='*80}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*80}\n")

    print(f"File: {file_path}")
    print(f"Total lines: {results['total_lines']}")
    print(f"  - Comment lines: {results['comment_lines']}")
    print(f"  - Blank lines: {results['blank_lines']}")
    print(f"  - URL lines: {results['valid_urls'] + results['invalid_urls']}")
    print()

    print(f"Valid URLs: {results['valid_urls']}")
    print(f"Invalid URLs: {results['invalid_urls']}")
    print(f"Duplicate UUIDs: {results['duplicates']}")
    print()

    # Print errors
    if results["errors"]:
        print(f"[ERRORS] Found {len(results['errors'])} error(s):")
        for error in results["errors"]:
            print(f"  - {error}")
        print()
        results["valid"] = False

    # Print warnings
    if results["warnings"]:
        print(f"[WARNINGS] Found {len(results['warnings'])} warning(s):")
        for warning in results["warnings"]:
            print(f"  - {warning}")
        print()

    # Final verdict
    if results["valid"] and results["valid_urls"] > 0:
        print(f"✅ VALID - {results['valid_urls']} unique URL(s) ready for discovery")
    elif results["valid"] and results["valid_urls"] == 0:
        print("⚠️  EMPTY - No URLs found in file (only comments/blanks)")
        print("    File is valid but has no match-center URLs to process")
    else:
        print("❌ INVALID - Fix errors before running discovery")

    print()

    return results


def validate_all_files(file_paths: list[Path]) -> dict:
    """Validate multiple URL files

    Args:
        file_paths: List of file paths to validate

    Returns:
        Dict with aggregated results
    """
    print(f"\n{'#'*80}")
    print("# LNB URL FILE VALIDATION")
    print(f"# Files: {len(file_paths)}")
    print(f"{'#'*80}\n")

    all_results = []
    total_valid_urls = 0
    total_invalid_urls = 0
    total_duplicates = 0
    files_with_errors = 0

    for file_path in file_paths:
        results = validate_file(file_path)
        all_results.append(results)

        total_valid_urls += results["valid_urls"]
        total_invalid_urls += results["invalid_urls"]
        total_duplicates += results["duplicates"]

        if not results["valid"]:
            files_with_errors += 1

    # Print overall summary
    print(f"{'='*80}")
    print("  OVERALL SUMMARY")
    print(f"{'='*80}\n")

    print(f"Files validated: {len(file_paths)}")
    print(f"  - Valid: {len(file_paths) - files_with_errors}")
    print(f"  - Invalid: {files_with_errors}")
    print()

    print("Total URLs across all files:")
    print(f"  - Valid: {total_valid_urls}")
    print(f"  - Invalid: {total_invalid_urls}")
    print(f"  - Duplicates: {total_duplicates}")
    print()

    if files_with_errors == 0 and total_valid_urls > 0:
        print(f"✅ ALL VALID - {total_valid_urls} total URL(s) ready for discovery")
    elif files_with_errors == 0 and total_valid_urls == 0:
        print("⚠️  ALL EMPTY - No URLs found in any file")
    else:
        print(f"❌ ERRORS FOUND - Fix {files_with_errors} file(s) before proceeding")

    print()

    return {
        "total_files": len(file_paths),
        "valid_files": len(file_paths) - files_with_errors,
        "invalid_files": files_with_errors,
        "total_valid_urls": total_valid_urls,
        "total_invalid_urls": total_invalid_urls,
        "total_duplicates": total_duplicates,
        "all_valid": files_with_errors == 0 and total_valid_urls > 0,
    }


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Validate LNB match-center URL files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate single file
    python tools/lnb/validate_url_file.py tools/lnb/urls_2024_2025.txt

    # Validate all season files
    python tools/lnb/validate_url_file.py tools/lnb/urls_*.txt

    # Validate multiple specific files
    python tools/lnb/validate_url_file.py \\
        tools/lnb/urls_2023_2024.txt \\
        tools/lnb/urls_2024_2025.txt

Exit Codes:
    0 - All files valid with URLs found
    1 - Errors found or no URLs in files
        """,
    )

    parser.add_argument("files", nargs="+", help="URL file(s) to validate")

    args = parser.parse_args()

    # Convert to Path objects
    file_paths = [Path(f) for f in args.files]

    # Validate
    if len(file_paths) == 1:
        results = validate_file(file_paths[0])
        exit_code = 0 if results["valid"] and results["valid_urls"] > 0 else 1
    else:
        overall = validate_all_files(file_paths)
        exit_code = 0 if overall["all_valid"] else 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
