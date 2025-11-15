#!/usr/bin/env python3
"""Decode the state parameter to understand its structure"""

import base64
import io
import json
import sys
import zlib
from pprint import pprint

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Different state parameters captured
STATES = {
    "pbp_view": "eJwtjEEKhDAMAL8iORtIGmNbH-AD_EFr2pMH2b0p_l0C3mZgmBv-sAxgXZgKKSoXQ-ZOWC1l3KOoUmrcKMM4wOFx_-G6uV1uZz2du7NoCDJpQ5E5fJscDWNtodoeS5oInhdqtRxC",
    "shots_view": "eJwtjMEJwzAMAFcJelcgWVFtd4AO0AWCbdnkUSgkeTVk9yLo847jTtjhMYENYSqkqFwMmQdhtZSxRVGl1LlThtsEb4_Hhs-X09dpXz_H0tayHa6GK9EQZNaOIvfwv-VoGGsP1VosaSa4fncmHy8",
}

print("=" * 80)
print("  DECODING STATE PARAMETERS")
print("=" * 80)
print()

for name, state in STATES.items():
    print(f"Decoding: {name}")
    print(f"State: {state}")
    print()

    # Try different decoding methods

    # Method 1: Base64url decode
    try:
        # Replace URL-safe characters
        state_standard = state.replace("-", "+").replace("_", "/")
        # Add padding if needed
        padding = 4 - (len(state_standard) % 4)
        if padding != 4:
            state_standard += "=" * padding

        decoded = base64.b64decode(state_standard)
        print(f"Base64 decoded (hex): {decoded.hex()}")
        print(f"Base64 decoded (bytes): {decoded[:100]}")

        # Try to interpret as text
        try:
            as_text = decoded.decode("utf-8")
            print(f"As UTF-8 text: {as_text}")
        except Exception:
            print("Not valid UTF-8 text")

        # Try to decompress (might be zlib/gzip compressed)
        try:
            decompressed = zlib.decompress(decoded)
            print(f"Zlib decompressed: {decompressed}")
            try:
                as_json = json.loads(decompressed)
                print("Decompressed JSON:")
                pprint(as_json)
            except Exception:
                pass
        except Exception:
            print("Not zlib compressed")

        # Try with different zlib parameters
        try:
            decompressed = zlib.decompress(decoded, -zlib.MAX_WBITS)  # Raw deflate
            print(f"Raw deflate decompressed: {decompressed}")
            try:
                as_json = json.loads(decompressed)
                print("Decompressed JSON:")
                pprint(as_json)
            except Exception:
                pass
        except Exception:
            pass

    except Exception as e:
        print(f"Error decoding: {e}")

    print()
    print("-" * 80)
    print()

# Try to find a pattern by comparing the two states
print("=" * 80)
print("  COMPARISON")
print("=" * 80)
print()

pbp_state = STATES["pbp_view"]
shots_state = STATES["shots_view"]

print(f"PBP state length: {len(pbp_state)}")
print(f"Shots state length: {len(shots_state)}")
print()

# Find common prefix/suffix
common_prefix_len = 0
for i in range(min(len(pbp_state), len(shots_state))):
    if pbp_state[i] == shots_state[i]:
        common_prefix_len = i + 1
    else:
        break

print(f"Common prefix length: {common_prefix_len}")
print(f"Common prefix: {pbp_state[:common_prefix_len]}")
print()

# Check if it might be a simple identifier
print("Hypothesis: The state might be:")
print("1. A compressed/encoded navigation state (which tab, filters, etc.)")
print("2. A simple view identifier that tells the server what data to include")
print("3. Related to the URL ~w parameter seen in the LNB site")
print()
print("Looking at the captured browser traffic, the state comes from the")
print("URL queryParams '~w' parameter, which seems to encode the current view.")
print()
