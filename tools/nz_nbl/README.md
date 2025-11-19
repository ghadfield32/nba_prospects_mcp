# NZ-NBL Game Index Tools

Tools for creating and maintaining the NZ-NBL game index required for data fetching.

## Overview

NZ-NBL data is fetched from FIBA LiveStats, which requires manually discovered game IDs. These tools help you:
1. Discover FIBA game IDs for NZ-NBL games
2. Build and maintain the game index
3. Validate game data

## Quick Start

### Step 1: Create Template

```bash
python tools/nz_nbl/create_game_index.py --create-template nz_nbl_games_template.csv
```

This creates a CSV template with example rows:

```csv
SEASON,GAME_ID,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE
2024,301234,2024-04-15,Auckland Tuatara,Wellington Saints,,
2024,301235,2024-04-16,Canterbury Rams,Otago Nuggets,85,78
```

### Step 2: Find FIBA Game IDs

**Manual Discovery (Required):**
1. Visit the FIBA LiveStats NZ-NBL page: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/
2. Browse to the season/competition you want
3. Click on individual games
4. Extract game ID from URL (e.g., `/u/NZN/301234/bs.html` → ID is `301234`)
5. Add game IDs to your CSV file

**Tips for Finding Game IDs:**
- Check the NZ-NBL official website for schedule information
- Use browser DevTools to inspect network requests on FIBA LiveStats
- Game IDs are typically 6-digit numbers
- Save URLs as you find them for future reference

### Step 3: Build the Index

Fill in your CSV file with discovered game IDs, then:

```bash
python tools/nz_nbl/create_game_index.py \
  --input nz_nbl_games_template.csv \
  --output data/nz_nbl_game_index.parquet
```

This will:
- Validate the CSV data
- Create a Parquet index file
- The index is now ready for use by NZ-NBL fetchers

### Step 4: Add Individual Games

You can add games one at a time:

```bash
python tools/nz_nbl/create_game_index.py --add-game \
  --game-id "301234" \
  --season "2024" \
  --date "2024-04-15" \
  --home "Auckland Tuatara" \
  --away "Wellington Saints" \
  --home-score 88 \
  --away-score 76
```

### Step 5: Validate Index

Check your index for errors:

```bash
python tools/nz_nbl/create_game_index.py \
  --validate data/nz_nbl_game_index.parquet
```

With FIBA LiveStats validation (slow):

```bash
python tools/nz_nbl/create_game_index.py \
  --validate data/nz_nbl_game_index.parquet \
  --check-fiba
```

## CSV Format

Required columns:
- `SEASON`: Season year (e.g., "2024")
- `GAME_ID`: FIBA LiveStats game ID (e.g., "301234")
- `GAME_DATE`: Game date in YYYY-MM-DD format
- `HOME_TEAM`: Home team name
- `AWAY_TEAM`: Away team name

Optional columns:
- `HOME_SCORE`: Home team final score
- `AWAY_SCORE`: Away team final score

## NZ-NBL Teams (2024 Season)

Common team names for reference:
- Auckland Tuatara
- Wellington Saints
- Canterbury Rams
- Otago Nuggets
- Taranaki Mountainairs
- Southland Sharks
- Nelson Giants
- Manawatu Jets
- Franklin Bulls
- Hawke's Bay Hawks

## Example Workflow

1. **Create template:**
   ```bash
   python tools/nz_nbl/create_game_index.py --create-template nz_nbl_2024.csv
   ```

2. **Manually discover game IDs** from FIBA LiveStats website

3. **Edit CSV** with discovered game IDs and team information

4. **Build index:**
   ```bash
   python tools/nz_nbl/create_game_index.py \
     --input nz_nbl_2024.csv \
     --output data/nz_nbl_game_index.parquet
   ```

5. **Validate:**
   ```bash
   python tools/nz_nbl/create_game_index.py --validate data/nz_nbl_game_index.parquet
   ```

6. **Use NZ-NBL fetchers** (they will automatically load the index)

## Troubleshooting

**Q: Where do I find FIBA game IDs?**
A: Visit https://fibalivestats.dcd.shared.geniussports.com/u/NZN/ and inspect game URLs

**Q: Can I automate game ID discovery?**
A: Unfortunately no - FIBA LiveStats doesn't provide a searchable API. Manual discovery is required.

**Q: How many games should I expect per season?**
A: NZ-NBL regular season typically has ~80-100 games plus playoffs

**Q: Can I use both CSV and Parquet formats?**
A: Yes, fetchers support both. Parquet is recommended for performance.

**Q: What if a game ID doesn't work?**
A: Use `--check-fiba` to validate game IDs against FIBA LiveStats

## See Also

- [NZ-NBL Fetcher Documentation](../../src/cbb_data/fetchers/nz_nbl_fiba.py)
- [FIBA LiveStats](https://fibalivestats.dcd.shared.geniussports.com/)
- [NZ-NBL Official Website](https://nznbl.basketball/)
