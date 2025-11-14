# FIBA Game Index Builder Tools

Tools for discovering and validating FIBA LiveStats game IDs from official league websites.

## Overview

These tools build game indexes (CSV files) that map season games to their FIBA LiveStats IDs. The indexes are used by league fetchers to retrieve box scores, play-by-play, and shot data.

## Supported Leagues

- **BCL** (Basketball Champions League)
- **BAL** (Basketball Africa League)
- **ABA** (ABA League / Adriatic League)
- **LKL** (Lithuanian Basketball League)

## Output Format

CSV files saved to `data/game_indexes/{LEAGUE}_{SEASON}.csv` with columns:

```csv
LEAGUE,SEASON,GAME_ID,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE,COMPETITION_PHASE,ROUND,VERIFIED
BCL,2023-24,123456,2023-10-15,Team A,Team B,85,72,RS,1,True
```

## Usage

### Build Single League/Season

```bash
python tools/fiba/build_game_index.py --league BCL --season 2023-24
```

### Build With Validation

Validates each game ID by fetching its HTML widget (slower but ensures accuracy):

```bash
python tools/fiba/build_game_index.py --league BCL --season 2023-24 --validate
```

### Validate Existing Index

```bash
python tools/fiba/build_game_index.py --league BCL --season 2023-24 --validate-only
```

### Build All Leagues (Current Season)

```bash
python tools/fiba/build_game_index.py --all-leagues
```

## Implementation Status

### ✅ Core Infrastructure
- Game index builder framework
- FIBA LiveStats ID extraction from HTML
- Game ID validation via HTML widget
- CSV output with metadata

### 🚧 League-Specific Scrapers
- **BCL**: Placeholder (requires BCL site inspection)
- **BAL**: Placeholder (requires BAL site inspection)
- **ABA**: Placeholder (requires ABA site inspection)
- **LKL**: Placeholder (requires LKL site inspection)

## Extending for New Leagues

To add a new league:

1. Add league URL to `LEAGUE_SITES` dict in `build_game_index.py`
2. Implement `build_{league}_index()` method in `FibaGameIndexBuilder`
3. Inspect the league's website to find:
   - Schedule/games page URL
   - Links containing `fibalivestats.dcd.shared.geniussports.com`
   - Game ID extraction pattern (usually in URL path)
4. Extract game context (date, teams, scores) from surrounding DOM
5. Test with `--validate` flag to ensure IDs are correct

## Manual Game Index Creation

If automated scraping isn't feasible for a league, you can manually create the CSV:

1. Visit the league's official website
2. For each game, find the "Live Stats" or "Box Score" link
3. Extract the game ID from the FIBA LiveStats URL:
   - Pattern: `fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE}/{GAME_ID}/bs.html`
   - Extract the numeric `{GAME_ID}`
4. Create CSV with required columns (see format above)
5. Save to `data/game_indexes/{LEAGUE}_{SEASON}.csv`
6. Validate: `python tools/fiba/build_game_index.py --league {LEAGUE} --season {SEASON} --validate-only`

## Rate Limiting

The tool respects rate limits:
- 1 second between page fetches
- 0.5 seconds between validation requests
- Configurable via `--rate-limit` flag (future enhancement)

## Error Handling

- **403 Access Denied**: May need to adjust headers or use different approach (manual CSV)
- **Network Errors**: Automatically retried with exponential backoff
- **Invalid Game IDs**: Logged and marked as `verified=False` in output

## Examples

### BCL 2023-24 Season

```bash
# Build index
python tools/fiba/build_game_index.py --league BCL --season 2023-24 --validate

# Verify output
cat data/game_indexes/BCL_2023_24.csv | head -5
```

Expected output:
```
LEAGUE,SEASON,GAME_ID,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE,COMPETITION_PHASE,ROUND,VERIFIED
BCL,2023-24,123456,2023-10-15,Team A,Team B,85,72,RS,1,True
BCL,2023-24,123457,2023-10-15,Team C,Team D,90,88,RS,1,True
```

## Troubleshooting

### No Game IDs Found

If the tool finds 0 game IDs:

1. Check if the league website URL is correct in `LEAGUE_SITES`
2. Inspect the website manually in a browser
3. Look for links containing `fibalivestats` in the HTML source
4. The site might be using JavaScript to load content - consider manual CSV creation

### Validation Failures

If many games show `verified=False`:

1. Check if the FIBA LiveStats URL pattern is correct
2. Try manually visiting a failed game ID: `https://fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE}/{GAME_ID}/bs.html`
3. The game might not be in the FIBA system yet (scheduled but not played)
4. The league code might be wrong (e.g., use "ABAL" instead of "ABA")

## Dependencies

- `requests`: HTTP client
- `beautifulsoup4`: HTML parsing
- `pandas`: DataFrame operations

Install with:
```bash
pip install requests beautifulsoup4 pandas
```

## Related Files

- `src/cbb_data/fetchers/fiba_livestats_json.py` - JSON client that uses game indexes
- `src/cbb_data/fetchers/fiba_html_common.py` - HTML fallback scraper
- `src/cbb_data/fetchers/bcl.py` - BCL league fetcher
- `src/cbb_data/fetchers/bal.py` - BAL league fetcher
- `src/cbb_data/fetchers/aba.py` - ABA league fetcher
- `src/cbb_data/fetchers/lkl.py` - LKL league fetcher

## Last Updated

2025-11-14

## Maintainer

Data Engineering Team
