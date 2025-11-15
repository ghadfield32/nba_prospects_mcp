# LNB Pro A Dataset Catalog

**Generated**: 2025-11-15 07:15:25

This document catalogs all available and missing datasets for LNB Pro A (French professional basketball).

---

## Summary

- **Implemented**: 11 datasets
- **Partial**: 2 datasets
- **Missing**: 3 datasets
- **Total**: 16 datasets

### By Category

- **Game Detail**: 8 datasets
- **Schedule**: 2 datasets
- **Season Stats**: 3 datasets
- **Structure**: 3 datasets

---

## Implemented Datasets

### Schedule

- **Category**: schedule
- **Source**: web_scraper
- **Granularity**: game
- **Historical Coverage**: 2015-present (via web scraping)
- **Test Result**: success
- **Sample Size**: 16 rows
- **Columns** (15): POS, Nom, MJLes matchs sont classés du plus récent (gauche) au plus ancien (droite), V-DLes matchs sont classés du plus récent (gauche) au plus ancien (droite), %VLes matchs sont classés du plus récent (gauche) au plus ancien (droite), PS-POLes matchs sont classés du plus récent (gauche) au plus ancien (droite), +/-Les matchs sont classés du plus récent (gauche) au plus ancien (droite), D (V-D)Les matchs sont classés du plus récent (gauche) au plus ancien (droite), E (V-D)Les matchs sont classés du plus récent (gauche) au plus ancien (droite), 5 DERNIERSLes matchs sont classés du plus récent (gauche) au plus ancien (droite), ... (+5 more)
- **Notes**: Scraped from lnb.fr/pro-a/calendrier using Playwright. Returns placeholder IDs, not fixture UUIDs.

### Play-by-Play

- **Category**: game_detail
- **Source**: atrium_api
- **Granularity**: event
- **Historical Coverage**: Current season only (2024-25)
- **Test Result**: success
- **Sample Size**: 544 rows
- **Columns** (17): GAME_ID, EVENT_ID, PERIOD_ID, CLOCK, EVENT_TYPE, EVENT_SUBTYPE, PLAYER_ID, PLAYER_NAME, PLAYER_JERSEY, TEAM_ID, ... (+7 more)
- **Notes**: Fetched from Atrium Sports API. Requires fixture UUID from match-center URLs. ~629 events/game, 12 event types.

### Shot Chart

- **Category**: game_detail
- **Source**: atrium_api
- **Granularity**: shot_attempt
- **Historical Coverage**: Current season only (2024-25)
- **Test Result**: success
- **Sample Size**: 136 rows
- **Columns** (16): GAME_ID, EVENT_ID, PERIOD_ID, CLOCK, SHOT_TYPE, SHOT_SUBTYPE, PLAYER_ID, PLAYER_NAME, PLAYER_JERSEY, TEAM_ID, ... (+6 more)
- **Notes**: Fetched from Atrium Sports API. Requires fixture UUID. ~123 shots/game, coordinates on 0-100 scale.

### Calendar by Division

- **Category**: schedule
- **Source**: lnb_api
- **Granularity**: game
- **Historical Coverage**: Unknown (API endpoint exists)
- **Test Result**: success
- **Sample Size**: 8 rows
- **Notes**: Endpoint: GET /match/getCalenderByDivision. Returns full season schedule for a division.

### Team Comparison

- **Category**: game_detail
- **Source**: lnb_api
- **Granularity**: game
- **Historical Coverage**: Unknown
- **Test Result**: error
- **Notes**: Endpoint: GET /stats/getTeamComparison. Pre-match team stats comparison.

### Last 5 Home/Away

- **Category**: game_detail
- **Source**: lnb_api
- **Granularity**: game
- **Historical Coverage**: Unknown
- **Test Result**: error
- **Notes**: Endpoint: GET /stats/getLastFiveMatchesHomeAway. Recent form for each team.

### Head to Head

- **Category**: game_detail
- **Source**: lnb_api
- **Granularity**: matchup
- **Historical Coverage**: Unknown
- **Test Result**: error
- **Notes**: Endpoint: GET /stats/getLastFiveMatchesHeadToHead. Recent head-to-head results.

### Match Officials

- **Category**: game_detail
- **Source**: lnb_api
- **Granularity**: game
- **Historical Coverage**: Unknown
- **Test Result**: error
- **Notes**: Endpoint: GET /stats/getMatchOfficialsPreGame. Referee assignments.

### Competition Teams

- **Category**: structure
- **Source**: lnb_api
- **Granularity**: team
- **Historical Coverage**: Unknown
- **Test Result**: error
- **Notes**: Endpoint: GET /stats/getCompetitionTeams. Teams in a competition.

### Live Match

- **Category**: game_detail
- **Source**: lnb_api
- **Granularity**: game
- **Historical Coverage**: Live games only
- **Test Result**: success
- **Sample Size**: 7 rows
- **Notes**: Endpoint: GET /match/getLiveMatch. Currently live games.

### Main Competitions

- **Category**: structure
- **Source**: lnb_api
- **Granularity**: competition
- **Historical Coverage**: By year
- **Test Result**: error
- **Notes**: Endpoint: GET /common/getMainCompetition. Available competitions for a year.

---

## Partial Datasets

### Player Season Stats

- **Category**: season_stats
- **Source**: lnb_api
- **Status**: Partially implemented
- **Notes**: get_persons_leaders endpoint exists but returns leaders only, not all players.

### Standings

- **Category**: season_stats
- **Source**: lnb_api
- **Status**: Partially implemented
- **Notes**: get_standing endpoint exists (POST /altrstats/getStanding) but needs testing.

---

## Missing Datasets

### Boxscore (Player-Game Stats)

- **Category**: game_detail
- **Expected Source**: lnb_api
- **Expected Granularity**: player-game
- **Notes**: Placeholder in LNB API client. Endpoint path unknown. Needs DevTools discovery.

### Team Season Stats

- **Category**: season_stats
- **Expected Source**: lnb_api
- **Expected Granularity**: team-season
- **Notes**: No endpoint discovered yet.

### Team Rosters

- **Category**: structure
- **Expected Source**: lnb_api
- **Expected Granularity**: player-team-season
- **Notes**: No endpoint discovered yet.

---

## Data Source Legend

- **lnb_api**: Official LNB API (api-prod.lnb.fr)
- **atrium_api**: Atrium Sports API (third-party stats provider)
- **web_scraper**: Playwright-based web scraping from lnb.fr
