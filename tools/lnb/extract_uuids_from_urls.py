#!/usr/bin/env python3
"""Extract fixture UUIDs from LNB match center URLs

Simple utility to extract and validate UUIDs from URLs or raw text.
Useful for batch processing URLs copied from the browser.

Usage:
    # From file
    uv run python tools/lnb/extract_uuids_from_urls.py --from-file urls.txt

    # From stdin
    echo "https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1" | \
        uv run python tools/lnb/extract_uuids_from_urls.py

    # From command line
    uv run python tools/lnb/extract_uuids_from_urls.py \
        "https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1" \
        "https://lnb.fr/fr/pre-match-center?mid=0cd1323f-6715-11f0-86f4-27e6e78614e1"

Output:
    - Prints extracted UUIDs (one per line)
    - Optionally saves to file with --output
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# UUID EXTRACTION
# ==============================================================================

# UUID regex pattern (36 characters: 8-4-4-4-12)
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def extract_uuid_from_text(text: str) -> str | None:
    """Extract fixture UUID from URL or raw text

    Supports multiple URL formats:
    - https://lnb.fr/fr/match-center/{uuid}
    - https://lnb.fr/fr/pre-match-center?mid={uuid}
    - https://www.lnb.fr/pro-a/match/{uuid}
    - Raw UUID string

    Args:
        text: URL or raw UUID string

    Returns:
        Extracted UUID (lowercase) or None if not found
    """
    text = text.strip()

    # Try to parse as URL first
    if text.startswith("http"):
        try:
            parsed = urlparse(text)

            # Check query parameters (e.g., ?mid=uuid)
            query_params = parse_qs(parsed.query)
            for param_name in ["mid", "match_id", "id", "uuid", "fixture_id"]:
                if param_name in query_params:
                    uuid_candidate = query_params[param_name][0]
                    if UUID_PATTERN.fullmatch(uuid_candidate):
                        return uuid_candidate.lower()

            # Check URL path (e.g., /match-center/uuid)
            path_parts = parsed.path.split("/")
            for part in reversed(path_parts):  # Check from end
                if UUID_PATTERN.fullmatch(part):
                    return part.lower()

        except Exception as e:
            print(f"[WARN] Failed to parse URL: {text} ({e})", file=sys.stderr)

    # Try direct UUID match
    match = UUID_PATTERN.search(text)
    if match:
        return match.group(0).lower()

    return None


def extract_uuids_from_text_list(texts: list[str], verbose: bool = False) -> list[str]:
    """Extract and deduplicate UUIDs from a list of URLs/text

    Args:
        texts: List of URLs or raw UUID strings
        verbose: If True, print warnings for failed extractions

    Returns:
        Deduplicated list of valid UUIDs (preserves order)
    """
    uuids = []

    for text in texts:
        if not text.strip():
            continue

        uuid = extract_uuid_from_text(text)
        if uuid:
            uuids.append(uuid)
        elif verbose:
            print(f"[WARN] Could not extract UUID from: {text}", file=sys.stderr)

    # Deduplicate while preserving order
    seen = set()
    unique_uuids = []
    for uuid in uuids:
        if uuid not in seen:
            seen.add(uuid)
            unique_uuids.append(uuid)

    return unique_uuids


def validate_uuid_format(uuid: str) -> bool:
    """Validate UUID format

    Args:
        uuid: UUID string to validate

    Returns:
        True if valid UUID format
    """
    return UUID_PATTERN.fullmatch(uuid) is not None


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Extract fixture UUIDs from LNB match center URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # From file
    uv run python tools/lnb/extract_uuids_from_urls.py --from-file urls.txt

    # From stdin
    cat urls.txt | uv run python tools/lnb/extract_uuids_from_urls.py

    # From command line arguments
    uv run python tools/lnb/extract_uuids_from_urls.py \\
        "https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1" \\
        "https://lnb.fr/fr/pre-match-center?mid=0cd1323f-6715-11f0-86f4-27e6e78614e1"

Supported URL formats:
    - https://lnb.fr/fr/match-center/{uuid}
    - https://lnb.fr/fr/pre-match-center?mid={uuid}
    - https://www.lnb.fr/pro-a/match/{uuid}
    - Raw UUID string
        """,
    )

    parser.add_argument(
        "urls", nargs="*", help="URLs or UUIDs to process (if not using --from-file or stdin)"
    )

    parser.add_argument(
        "--from-file", type=str, default=None, help="Read URLs from file (one per line)"
    )

    parser.add_argument(
        "--output", type=str, default=None, help="Save extracted UUIDs to file (one per line)"
    )

    parser.add_argument(
        "--validate", action="store_true", help="Validate UUID format only (no extraction)"
    )

    parser.add_argument(
        "--verbose", action="store_true", help="Print warnings for failed extractions"
    )

    args = parser.parse_args()

    # Collect input from various sources
    input_texts = []

    # 1. From file
    if args.from_file:
        try:
            with open(args.from_file, encoding="utf-8") as f:
                input_texts.extend(line.strip() for line in f if line.strip())
            if args.verbose:
                print(
                    f"[INFO] Loaded {len(input_texts)} lines from {args.from_file}", file=sys.stderr
                )
        except Exception as e:
            print(f"[ERROR] Failed to read from file: {e}", file=sys.stderr)
            sys.exit(1)

    # 2. From command line arguments
    if args.urls:
        input_texts.extend(args.urls)

    # 3. From stdin (if no file and no args)
    if not input_texts and not sys.stdin.isatty():
        input_texts.extend(line.strip() for line in sys.stdin if line.strip())
        if args.verbose:
            print(f"[INFO] Loaded {len(input_texts)} lines from stdin", file=sys.stderr)

    # Validate input
    if not input_texts:
        print("[ERROR] No input provided", file=sys.stderr)
        print("Usage: Provide URLs via --from-file, command line args, or stdin", file=sys.stderr)
        sys.exit(1)

    # Validate mode vs extract mode
    if args.validate:
        # Validate only
        valid_count = 0
        for text in input_texts:
            if validate_uuid_format(text.strip()):
                print(text.strip())
                valid_count += 1
            elif args.verbose:
                print(f"[INVALID] {text}", file=sys.stderr)

        if args.verbose:
            print(f"\n[SUMMARY] {valid_count}/{len(input_texts)} valid UUIDs", file=sys.stderr)

    else:
        # Extract UUIDs
        uuids = extract_uuids_from_text_list(input_texts, verbose=args.verbose)

        if args.verbose:
            print(
                f"\n[SUMMARY] Extracted {len(uuids)} unique UUIDs from {len(input_texts)} inputs",
                file=sys.stderr,
            )

        # Save to file
        if args.output:
            try:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f:
                    for uuid in uuids:
                        f.write(f"{uuid}\n")

                if args.verbose:
                    print(f"[SAVED] {len(uuids)} UUIDs to {args.output}", file=sys.stderr)

            except Exception as e:
                print(f"[ERROR] Failed to save to file: {e}", file=sys.stderr)
                sys.exit(1)

        # Print to stdout (unless saved to file)
        if not args.output:
            for uuid in uuids:
                print(uuid)


if __name__ == "__main__":
    main()
