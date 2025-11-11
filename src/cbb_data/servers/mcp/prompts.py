"""
MCP Prompt templates for common basketball data queries.

Prompts are pre-built query templates that LLMs can use for common tasks.
"""

# ============================================================================
# Prompt Templates
# ============================================================================

PROMPTS = [
    {
        "name": "top-scorers",
        "description": "Get the top scorers for a league and season",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {"name": "season", "description": "Season year (e.g., '2025')", "required": True},
            {
                "name": "limit",
                "description": "Number of top scorers to return (default: 20)",
                "required": False,
            },
        ],
        "template": """Find the top {limit} scorers in {league} for the {season} season.

Use the get_player_season_stats tool with:
- league: {league}
- season: {season}
- per_mode: "PerGame"
- limit: {limit}

Sort the results by points per game (PTS or PPG column) in descending order and present them in a table format showing:
- Player name
- Team
- Points per game
- Games played
- Field goal percentage

Include a brief analysis of the scoring leaders and any notable trends.""",
    },
    {
        "name": "team-schedule",
        "description": "Get the full schedule for a specific team",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {"name": "team", "description": "Team name", "required": True},
            {"name": "season", "description": "Season year (optional)", "required": False},
        ],
        "template": """Get the schedule for {team} in {league}{season_text}.

Use the get_schedule tool with:
- league: {league}
- team: ["{team}"]
{season_param}

Present the results showing:
- Game date
- Opponent
- Location (home/away)
- Result (if game completed)
- Score (if game completed)

Organize by chronological order and highlight upcoming games vs completed games.""",
    },
    {
        "name": "recent-games",
        "description": "Get recent games across a league",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {
                "name": "days",
                "description": "Number of days to look back (default: 2)",
                "required": False,
            },
        ],
        "template": """Get recent games for {league} over the last {days} days.

Use the get_recent_games tool with:
- league: {league}
- days: {days}

Present the results grouped by date showing:
- Game date
- Matchup (home vs away)
- Final score
- Notable performances (if available)

Highlight any upsets or particularly close games.""",
    },
    {
        "name": "player-game-log",
        "description": "Get game-by-game statistics for a specific player",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {"name": "player", "description": "Player name", "required": True},
            {"name": "season", "description": "Season year (optional)", "required": False},
            {
                "name": "limit",
                "description": "Number of games to return (default: 10)",
                "required": False,
            },
        ],
        "template": """Get the game log for {player} in {league}{season_text}.

Use the get_player_game_stats tool with:
- league: {league}
- player: ["{player}"]
{season_param}
- limit: {limit}

Present the results in chronological order showing:
- Game date
- Opponent
- Minutes played
- Points
- Rebounds
- Assists
- Shooting percentages

Include a brief statistical summary and identify their best performances.""",
    },
    {
        "name": "team-standings",
        "description": "Get team standings and season statistics",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {"name": "season", "description": "Season year (e.g., '2025')", "required": True},
            {
                "name": "division",
                "description": "Division filter for NCAA (D1, D2, D3) - optional",
                "required": False,
            },
        ],
        "template": """Get team standings for {league}{division_text} in the {season} season.

Use the get_team_season_stats tool with:
- league: {league}
- season: {season}
{division_param}

Present the results sorted by win percentage showing:
- Team name
- Wins
- Losses
- Win percentage
- Points per game (if available)

Identify the top teams and any notable trends in the standings.""",
    },
    {
        "name": "player-comparison",
        "description": "Compare statistics between multiple players",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {
                "name": "players",
                "description": "Comma-separated list of player names",
                "required": True,
            },
            {"name": "season", "description": "Season year (e.g., '2025')", "required": True},
        ],
        "template": """Compare the following players in {league} for the {season} season: {players}

Use the get_player_season_stats tool with:
- league: {league}
- season: {season}
- player: {players_array}
- per_mode: "PerGame"

Create a comparison table showing:
- Player name
- Team
- Points per game
- Rebounds per game
- Assists per game
- Field goal percentage
- Games played

Provide analysis comparing their strengths, weaknesses, and overall impact.""",
    },
    {
        "name": "head-to-head",
        "description": "Get head-to-head matchup history between two teams",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {"name": "team1", "description": "First team name", "required": True},
            {"name": "team2", "description": "Second team name", "required": True},
            {"name": "season", "description": "Season year (optional)", "required": False},
        ],
        "template": """Get the head-to-head matchup history between {team1} and {team2} in {league}{season_text}.

First, use the get_schedule tool to get games for {team1}:
- league: {league}
- team: ["{team1}"]
{season_param}

Then filter the results to find games where {team2} was the opponent.

Present the results showing:
- Game date
- Location (home/away)
- Final score
- Margin of victory

Summarize the head-to-head record and identify any patterns or trends.""",
    },
    {
        "name": "breakout-players",
        "description": "Identify breakout players showing significant improvement",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            },
            {
                "name": "current_season",
                "description": "Current season year (e.g., '2025')",
                "required": True,
            },
            {
                "name": "team",
                "description": "Specific team to analyze (optional)",
                "required": False,
            },
        ],
        "template": """Identify breakout players in {league} for the {current_season} season{team_text}.

Use the get_player_season_stats tool with:
- league: {league}
- season: {current_season}
- per_mode: "PerGame"
{team_param}
- limit: 100

Analyze players showing significant improvement by looking for:
- High scoring averages (15+ PPG)
- Efficient shooting (>45% FG%)
- Well-rounded contributions (points, rebounds, assists)
- Players with potential draft/transfer portal interest

Present the top 10 breakout candidates with their key statistics and explain what makes them stand out.""",
    },
    {
        "name": "todays-games",
        "description": "Get today's games and recent results",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)",
                "required": True,
            }
        ],
        "template": """Get today's games and recent results for {league}.

Use the get_recent_games tool with:
- league: {league}
- days: 2

Present the results in two sections:
1. **Completed Games** (from yesterday/earlier today):
   - Matchup and final score
   - Key performances

2. **Upcoming Games** (today):
   - Matchup and scheduled time
   - Team records/standings if available

Highlight any notable matchups or surprising results.""",
    },
    {
        "name": "conference-leaders",
        "description": "Get statistical leaders for a conference or division",
        "arguments": [
            {
                "name": "league",
                "description": "League identifier (must be NCAA-MBB or NCAA-WBB)",
                "required": True,
            },
            {"name": "season", "description": "Season year (e.g., '2025')", "required": True},
            {"name": "division", "description": "Division (D1, D2, or D3)", "required": False},
        ],
        "template": """Get statistical leaders for {league} {division_text}in the {season} season.

Use the get_player_season_stats tool with:
- league: {league}
- season: {season}
- per_mode: "PerGame"
{division_param}
- limit: 50

Identify leaders in multiple categories:
- **Scoring Leaders**: Top 5 in PPG
- **Rebounding Leaders**: Top 5 in RPG
- **Assists Leaders**: Top 5 in APG
- **Shooting Efficiency**: Top 5 in FG%

Present each category in a separate table and identify any players who appear in multiple categories.""",
    },
]
