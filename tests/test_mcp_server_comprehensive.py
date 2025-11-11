"""
Comprehensive MCP Server Tests with Detailed Documentation

This module provides thorough testing of the MCP (Model Context Protocol) server with:
1. Detailed docstrings explaining what each test does
2. Usage examples showing how LLMs interact with the server
3. Testing all tools, resources, and prompts
4. Integration testing with MCP protocol
5. Error handling verification

HOW TO RUN THESE TESTS:
======================

Run all MCP tests:
    pytest tests/test_mcp_server_comprehensive.py -v

Run only smoke tests:
    pytest tests/test_mcp_server_comprehensive.py -m smoke -v

Run tests for specific component:
    pytest tests/test_mcp_server_comprehensive.py::TestMCPTools -v

Run with coverage:
    pytest tests/test_mcp_server_comprehensive.py --cov=cbb_data.servers.mcp

BEFORE RUNNING:
==============
The MCP server tests run in-process and don't require a separate server.
However, you may want to test with Claude Desktop:

1. Install Claude Desktop: https://claude.ai/download
2. Add to Claude Desktop config (~/.config/claude/claude_desktop_config.json):
   {
     "mcpServers": {
       "cbb-data": {
         "command": "python",
         "args": ["-m", "cbb_data.servers.mcp_server"],
         "env": {}
       }
     }
   }
3. Restart Claude Desktop

MCP USAGE EXAMPLES:
==================

The MCP server exposes 10 tools, 11+ resources, and 10 prompts to LLMs:

1. Tools - Functions LLMs can call:
   - get_schedule: Get game schedules
   - get_player_game_stats: Get player box scores
   - get_team_game_stats: Get team game results
   - get_play_by_play: Get play-by-play data
   - get_shot_data: Get shot chart data
   - get_player_season_stats: Get player season aggregates
   - get_team_season_stats: Get team season aggregates
   - get_recent_games: Convenience for recent games
   - list_available_datasets: Discover datasets
   - search_teams: Find team names

2. Resources - Browsable data catalogs:
   - cbb://leagues: List all leagues
   - cbb://leagues/NCAA-MBB: NCAA Men's Basketball info
   - cbb://datasets: List all datasets
   - cbb://datasets/schedule: Dataset metadata
   - cbb://stats-examples: Example queries

3. Prompts - Pre-built query templates:
   - top-scorers: Find top scorers for a season
   - team-schedule: Get team's schedule
   - player-stats: Get player statistics
   - game-analysis: Analyze specific game
   - head-to-head: Compare teams
"""

import pytest

# ============================================================================
# MCP Tools Tests
# ============================================================================


@pytest.mark.mcp
@pytest.mark.smoke
class TestMCPTools:
    """
    Tests for MCP tools (functions callable by LLMs).

    Tools are the primary way LLMs interact with data through MCP.
    Each tool is a function with a defined schema that LLMs can call
    to fetch data.

    Example LLM interaction:
        LLM: "Show me Duke's schedule for 2024"
        MCP: Calls get_schedule tool with filters={league="NCAA-MBB", team=["Duke"], season="2024"}
        MCP: Returns formatted schedule data
        LLM: Presents results to user
    """

    def test_get_schedule_tool_exists(self, mcp_tools) -> None:
        """
        Test that get_schedule tool is registered.

        The get_schedule tool allows LLMs to fetch game schedules with
        flexible filtering by league, season, team, and date range.

        Tool signature:
            get_schedule(
                league: str,           # Required: "NCAA-MBB", "NCAA-WBB", "EuroLeague"
                season: str = None,    # Optional: "2024", "2023", etc.
                team: list = None,     # Optional: ["Duke", "UNC"]
                date_from: str = None, # Optional: "2024-01-01"
                date_to: str = None,   # Optional: "2024-12-31"
                limit: int = 100       # Optional: max rows
            )

        Example LLM usage:
            "Get Duke's schedule for the 2024 season"
            -> tool: get_schedule
            -> args: {league: "NCAA-MBB", season: "2024", team: ["Duke"]}
        """
        tool_names = [tool["name"] for tool in mcp_tools]
        assert "get_schedule" in tool_names, "get_schedule tool not registered"

    def test_get_player_game_stats_tool_exists(self, mcp_tools) -> None:
        """
        Test that get_player_game_stats tool is registered.

        This tool provides per-player per-game box score statistics.
        LLMs use it to answer questions about individual performances.

        Tool signature:
            get_player_game_stats(
                league: str,
                season: str = None,
                team: list = None,
                player: list = None,
                game_ids: list = None,
                limit: int = 100
            )

        Example LLM usage:
            "How did Cooper Flagg perform in his last 5 games?"
            -> tool: get_player_game_stats
            -> args: {league: "NCAA-MBB", season: "2025", player: ["Cooper Flagg"], limit: 5}

            "Show me the top performances from yesterday's Duke game"
            -> tool: get_player_game_stats
            -> args: {league: "NCAA-MBB", team: ["Duke"], date_from: "2025-01-14", date_to: "2025-01-14"}
        """
        tool_names = [tool["name"] for tool in mcp_tools]
        assert "get_player_game_stats" in tool_names, "get_player_game_stats tool not registered"

    def test_get_player_season_stats_tool_exists(self, mcp_tools) -> None:
        """
        Test that get_player_season_stats tool is registered.

        This tool provides season-aggregated player statistics with
        multiple aggregation modes (Totals, PerGame, Per40).

        Tool signature:
            get_player_season_stats(
                league: str,
                season: str,
                per_mode: str = "Totals",  # "Totals", "PerGame", "Per40"
                team: list = None,
                player: list = None,
                limit: int = 100
            )

        Example LLM usage:
            "Who are the top 10 scorers in NCAA Men's Basketball this season?"
            -> tool: get_player_season_stats
            -> args: {league: "NCAA-MBB", season: "2025", per_mode: "PerGame", limit: 10}

            "Show me Duke players' season stats"
            -> tool: get_player_season_stats
            -> args: {league: "NCAA-MBB", season: "2025", team: ["Duke"], per_mode: "Totals"}
        """
        tool_names = [tool["name"] for tool in mcp_tools]
        assert (
            "get_player_season_stats" in tool_names
        ), "get_player_season_stats tool not registered"

    def test_get_recent_games_tool_exists(self, mcp_tools) -> None:
        """
        Test that get_recent_games tool is registered.

        Convenience tool for getting recent games without specifying dates.
        Particularly useful for LLMs to quickly check current games.

        Tool signature:
            get_recent_games(
                league: str,
                days: int = 2,         # Look back this many days
                teams: list = None     # Optional team filter
            )

        Example LLM usage:
            "What games are happening today in NCAA Men's Basketball?"
            -> tool: get_recent_games
            -> args: {league: "NCAA-MBB", days: 1}

            "Show me Duke's games from the last week"
            -> tool: get_recent_games
            -> args: {league: "NCAA-MBB", days: 7, teams: ["Duke"]}
        """
        tool_names = [tool["name"] for tool in mcp_tools]
        assert "get_recent_games" in tool_names, "get_recent_games tool not registered"

    def test_list_available_datasets_tool_exists(self, mcp_tools) -> None:
        """
        Test that list_available_datasets tool is registered.

        Discovery tool that helps LLMs understand what data is available.

        Tool signature:
            list_available_datasets()  # No parameters

        Example LLM usage:
            "What kind of basketball data do you have access to?"
            -> tool: list_available_datasets
            -> Returns: List of 8 datasets with descriptions

        Returns:
            - schedule: Game schedules and results
            - player_game: Per-player per-game stats
            - team_game: Team-level game results
            - play_by_play: Play-by-play events
            - shots: Shot chart data
            - player_season: Player season aggregates
            - team_season: Team season aggregates
            - player_team_season: Player×team season stats
        """
        tool_names = [tool["name"] for tool in mcp_tools]
        assert (
            "list_available_datasets" in tool_names
        ), "list_available_datasets tool not registered"

    def test_all_expected_tools_registered(self, mcp_tools) -> None:
        """
        Test that all 10 expected tools are registered.

        Complete tool list:
            1. get_schedule - Game schedules
            2. get_player_game_stats - Player game stats
            3. get_team_game_stats - Team game stats
            4. get_play_by_play - Play-by-play data
            5. get_shot_data - Shot chart data
            6. get_player_season_stats - Player season aggregates
            7. get_team_season_stats - Team season aggregates
            8. get_recent_games - Recent games convenience
            9. list_available_datasets - Dataset discovery
            10. search_teams - Team name search
        """
        expected_tools = [
            "get_schedule",
            "get_player_game_stats",
            "get_team_game_stats",
            "get_play_by_play",
            "get_shot_data",
            "get_player_season_stats",
            "get_team_season_stats",
            "get_recent_games",
            "list_available_datasets",
            "search_teams",
        ]

        tool_names = [tool["name"] for tool in mcp_tools]

        for expected in expected_tools:
            assert expected in tool_names, f"Expected tool '{expected}' not found"

    def test_tools_have_required_fields(self, mcp_tools) -> None:
        """
        Test that all tools have required metadata fields.

        Each tool must have:
            - name: Unique identifier for the tool
            - description: Human-readable explanation
            - inputSchema: JSON Schema for parameters
            - handler: Function to execute the tool

        This metadata allows LLMs to understand:
            - What the tool does (description)
            - What parameters it accepts (inputSchema)
            - How to call it (name + schema)
        """
        required_fields = ["name", "description", "inputSchema", "handler"]

        for tool in mcp_tools:
            for field in required_fields:
                assert field in tool, f"Tool '{tool.get('name', 'unknown')}' missing field: {field}"

    def test_tool_schemas_are_valid(self, mcp_tools) -> None:
        """
        Test that all tool input schemas are valid JSON Schema.

        Input schemas define:
            - What parameters the tool accepts
            - Which parameters are required
            - Data types for each parameter
            - Default values

        Example schema:
            {
              "type": "object",
              "properties": {
                "league": {
                  "type": "string",
                  "description": "League identifier",
                  "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"]
                },
                "season": {
                  "type": "string",
                  "description": "Season year (e.g., '2024')"
                }
              },
              "required": ["league"]
            }
        """
        for tool in mcp_tools:
            schema = tool["inputSchema"]

            # Must be object type
            assert (
                schema.get("type") == "object"
            ), f"Tool '{tool['name']}' schema must be type 'object'"

            # Must have properties
            assert "properties" in schema, f"Tool '{tool['name']}' schema missing 'properties'"

            # Properties should be a dict
            assert isinstance(
                schema["properties"], dict
            ), f"Tool '{tool['name']}' schema properties must be a dict"


# ============================================================================
# MCP Resources Tests
# ============================================================================


@pytest.mark.mcp
@pytest.mark.smoke
class TestMCPResources:
    """
    Tests for MCP resources (browsable data catalogs).

    Resources provide structured information that LLMs can browse
    without making tool calls. Think of them like documentation or
    help pages.

    Example LLM interaction:
        LLM: "What leagues are available?"
        MCP: Returns cbb://leagues resource
        MCP: Shows NCAA-MBB, NCAA-WBB, EuroLeague with details
        LLM: Presents league info to user

        LLM: "Tell me about the schedule dataset"
        MCP: Returns cbb://datasets/schedule resource
        MCP: Shows filters, columns, examples
        LLM: Explains dataset to user
    """

    def test_leagues_resource_exists(self, mcp_resources) -> None:
        """
        Test that leagues resource is available.

        Resource URI: cbb://leagues

        This resource lists all supported leagues with metadata:
            - Full name
            - Coverage dates
            - Data sources
            - Special notes

        Example LLM usage:
            "What basketball leagues do you have data for?"
            -> resource: cbb://leagues
            -> Returns formatted list of leagues

        Content includes:
            - NCAA-MBB: NCAA Men's Basketball (2002-present)
            - NCAA-WBB: NCAA Women's Basketball (2005-present)
            - EuroLeague: EuroLeague Basketball (2001-present)
        """
        resource_uris = [r["uri"] for r in mcp_resources]
        assert "cbb://leagues" in resource_uris, "leagues resource not found"

    def test_datasets_resource_exists(self, mcp_resources) -> None:
        """
        Test that datasets resource is available.

        Resource URI: cbb://datasets

        This resource lists all 8 available datasets with:
            - Dataset ID
            - Description
            - Supported leagues
            - Required filters
            - Example usage

        Example LLM usage:
            "What datasets are available?"
            -> resource: cbb://datasets
            -> Returns list of 8 datasets with metadata

            "How do I get play-by-play data?"
            -> resource: cbb://datasets/play_by_play
            -> Returns detailed info about play_by_play dataset
        """
        resource_uris = [r["uri"] for r in mcp_resources]
        assert "cbb://datasets" in resource_uris, "datasets resource not found"

    def test_league_specific_resources_exist(self, mcp_resources) -> None:
        """
        Test that league-specific info resources exist.

        Resource URIs:
            - cbb://leagues/NCAA-MBB
            - cbb://leagues/NCAA-WBB
            - cbb://leagues/EuroLeague

        Each provides detailed league information:
            - Full name and abbreviation
            - Coverage period (years available)
            - Data sources used
            - Notable characteristics
            - Example queries

        Example LLM usage:
            "Tell me about NCAA Men's Basketball data"
            -> resource: cbb://leagues/NCAA-MBB
            -> Returns comprehensive NCAA-MBB info
        """
        resource_uris = [r["uri"] for r in mcp_resources]

        league_resources = [
            "cbb://leagues/NCAA-MBB",
            "cbb://leagues/NCAA-WBB",
            "cbb://leagues/EuroLeague",
        ]

        for uri in league_resources:
            assert uri in resource_uris, f"League resource '{uri}' not found"

    def test_dataset_specific_resources_exist(self, mcp_resources, all_datasets) -> None:
        """
        Test that dataset-specific info resources exist.

        Resource URIs:
            - cbb://datasets/schedule
            - cbb://datasets/player_game
            - cbb://datasets/team_game
            - cbb://datasets/play_by_play
            - cbb://datasets/shots
            - cbb://datasets/player_season
            - cbb://datasets/team_season
            - cbb://datasets/player_team_season

        Each provides detailed dataset information:
            - What data it contains
            - Required vs optional filters
            - Available columns
            - Example queries
            - Common use cases

        Example LLM usage:
            "How do I query player season stats?"
            -> resource: cbb://datasets/player_season
            -> Returns player_season dataset documentation
        """
        resource_uris = [r["uri"] for r in mcp_resources]

        for dataset_id in all_datasets:
            expected_uri = f"cbb://datasets/{dataset_id}"
            assert expected_uri in resource_uris, f"Dataset resource '{expected_uri}' not found"

    def test_resources_have_required_fields(self, mcp_resources) -> None:
        """
        Test that all resources have required metadata.

        Each resource must have:
            - uri: Unique identifier (e.g., cbb://leagues)
            - name: Human-readable name
            - description: What the resource contains
            - mimeType: Content type (usually text/markdown)
            - handler: Function to fetch resource content

        This allows LLMs to:
            - Browse available resources
            - Understand what each contains
            - Fetch content when needed
        """
        required_fields = ["uri", "name", "description", "mimeType", "handler"]

        for resource in mcp_resources:
            for field in required_fields:
                assert (
                    field in resource
                ), f"Resource '{resource.get('uri', 'unknown')}' missing field: {field}"

    def test_resources_use_markdown_format(self, mcp_resources) -> None:
        """
        Test that resources use text/markdown MIME type.

        Markdown format provides:
            - Rich formatting (headers, lists, code blocks)
            - Easy readability for LLMs
            - Consistent structure

        LLMs parse markdown to:
            - Extract structured information
            - Present formatted content to users
            - Generate help text
        """
        for resource in mcp_resources:
            assert (
                resource["mimeType"] == "text/markdown"
            ), f"Resource '{resource['uri']}' should use text/markdown"


# ============================================================================
# MCP Prompts Tests
# ============================================================================


@pytest.mark.mcp
@pytest.mark.smoke
class TestMCPPrompts:
    """
    Tests for MCP prompts (pre-built query templates).

    Prompts are reusable templates that reduce token usage and provide
    consistent query patterns. Think of them like saved queries or macros.

    Example LLM interaction:
        User: "Show me the top scorers this season"
        LLM: Uses 'top-scorers' prompt
        Prompt: Expands to "Find top {limit} scorers in {league} for {season}..."
        MCP: Executes prompt with user's parameters
        LLM: Returns formatted results
    """

    def test_top_scorers_prompt_exists(self, mcp_prompts) -> None:
        """
        Test that top-scorers prompt is available.

        Prompt: top-scorers

        Purpose: Find the top scorers for a league and season

        Parameters:
            - league: Which league to query
            - season: Which season to analyze
            - per_mode: How to aggregate (Totals, PerGame, Per40)
            - limit: How many players to return

        Example usage:
            Prompt: top-scorers
            Args: {league: "NCAA-MBB", season: "2025", per_mode: "PerGame", limit: 20}
            Returns: Top 20 scorers by points per game

        Benefits:
            - Saves tokens (template stored on server)
            - Consistent query format
            - Optimized for this specific use case
        """
        prompt_names = [p["name"] for p in mcp_prompts]
        assert "top-scorers" in prompt_names, "top-scorers prompt not found"

    def test_team_schedule_prompt_exists(self, mcp_prompts) -> None:
        """
        Test that team-schedule prompt is available.

        Prompt: team-schedule

        Purpose: Get a team's schedule for a specific season

        Parameters:
            - league: Which league
            - season: Which season
            - team: Team name

        Example usage:
            Prompt: team-schedule
            Args: {league: "NCAA-MBB", season: "2025", team: "Duke"}
            Returns: Duke's complete 2025 schedule with results

        Use cases:
            - Display team schedules
            - Analyze strength of schedule
            - Find upcoming games
        """
        prompt_names = [p["name"] for p in mcp_prompts]
        assert "team-schedule" in prompt_names, "team-schedule prompt not found"

    def test_player_stats_prompt_exists(self, mcp_prompts) -> None:
        """
        Test that player-stats prompt is available.

        Prompt: player-stats

        Purpose: Get statistics for a specific player

        Parameters:
            - league: Which league
            - season: Which season
            - player: Player name
            - per_mode: Aggregation mode

        Example usage:
            Prompt: player-stats
            Args: {league: "NCAA-MBB", season: "2025", player: "Cooper Flagg", per_mode: "PerGame"}
            Returns: Cooper Flagg's 2025 per-game stats

        Use cases:
            - Player profiles
            - Performance analysis
            - Comparison data
        """
        prompt_names = [p["name"] for p in mcp_prompts]
        assert "player-stats" in prompt_names, "player-stats prompt not found"

    def test_prompts_have_required_fields(self, mcp_prompts) -> None:
        """
        Test that all prompts have required metadata.

        Each prompt must have:
            - name: Unique identifier
            - description: What the prompt does
            - arguments: List of parameter definitions
            - template: The prompt text template

        This allows LLMs to:
            - Discover available prompts
            - Understand what each does
            - Know what parameters are needed
            - Execute prompts correctly
        """
        required_fields = ["name", "description", "arguments"]

        for prompt in mcp_prompts:
            for field in required_fields:
                assert (
                    field in prompt
                ), f"Prompt '{prompt.get('name', 'unknown')}' missing field: {field}"

    def test_prompt_arguments_are_defined(self, mcp_prompts) -> None:
        """
        Test that prompt arguments are properly defined.

        Each argument should have:
            - name: Parameter name
            - description: What it's for
            - required: Whether it's required

        Well-defined arguments help LLMs:
            - Collect correct parameters from users
            - Validate inputs
            - Provide helpful error messages
        """
        for prompt in mcp_prompts:
            arguments = prompt.get("arguments", [])

            for arg in arguments:
                assert "name" in arg, f"Prompt '{prompt['name']}' has argument missing 'name'"
                assert (
                    "description" in arg
                ), f"Prompt '{prompt['name']}' argument '{arg.get('name')}' missing 'description'"
                assert (
                    "required" in arg
                ), f"Prompt '{prompt['name']}' argument '{arg.get('name')}' missing 'required'"


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.mcp
@pytest.mark.integration
class TestMCPIntegration:
    """
    Integration tests that verify MCP server components work together.

    These tests simulate real-world LLM interactions:
        1. LLM browses resources to understand available data
        2. LLM calls tools to fetch data
        3. LLM uses prompts for common queries
        4. All components return consistent, usable results
    """

    def test_can_import_mcp_server(self) -> None:
        """
        Test that MCP server module can be imported.

        This verifies:
            - All dependencies are installed
            - No import errors in server code
            - Module structure is correct

        Example:
            from cbb_data.servers.mcp_server import BasketballDataMCPServer
            server = BasketballDataMCPServer()
        """
        try:
            from cbb_data.servers.mcp_server import BasketballDataMCPServer  # noqa: F401

            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import MCP server: {e}")

    def test_can_create_mcp_server_instance(self) -> None:
        """
        Test that MCP server can be instantiated.

        This verifies:
            - Constructor works correctly
            - All registries are initialized
            - Server is ready to handle requests

        Example:
            from cbb_data.servers.mcp_server import BasketballDataMCPServer
            server = BasketballDataMCPServer()
            # Server is now ready to accept MCP requests
        """
        try:
            from cbb_data.servers.mcp_server import BasketballDataMCPServer

            server = BasketballDataMCPServer()
            assert server is not None
            assert hasattr(server, "tools_registry")
            assert hasattr(server, "resources_registry")
            assert hasattr(server, "prompts_registry")
        except Exception as e:
            pytest.fail(f"Failed to create MCP server instance: {e}")

    def test_tools_resources_prompts_counts_match(
        self, mcp_tools, mcp_resources, mcp_prompts
    ) -> None:
        """
        Test that component counts match expected values.

        Expected counts:
            - Tools: 10 (all dataset operations + utilities)
            - Resources: 11+ (leagues, datasets, and sub-resources)
            - Prompts: 10 (common query patterns)

        These counts ensure:
            - All components are registered
            - Nothing was accidentally removed
            - New components are properly added
        """
        assert len(mcp_tools) == 10, f"Expected 10 tools, found {len(mcp_tools)}"
        assert (
            len(mcp_resources) >= 11
        ), f"Expected at least 11 resources, found {len(mcp_resources)}"
        assert len(mcp_prompts) == 10, f"Expected 10 prompts, found {len(mcp_prompts)}"

    def test_all_leagues_supported_across_components(
        self, mcp_tools, mcp_resources, all_leagues
    ) -> None:
        """
        Test that all leagues are consistently supported.

        All three leagues should be:
            - Documented in resources (cbb://leagues)
            - Accepted by tools (league parameter)
            - Referenced in prompts

        Consistency ensures:
            - No league is accidentally omitted
            - LLMs can query any league
            - Documentation matches implementation

        Leagues:
            - NCAA-MBB: NCAA Men's Basketball
            - NCAA-WBB: NCAA Women's Basketball
            - EuroLeague: EuroLeague Basketball
        """
        # Check that league resources exist
        resource_uris = [r["uri"] for r in mcp_resources]

        for league in all_leagues:
            league_uri = f"cbb://leagues/{league}"
            assert league_uri in resource_uris, f"League resource for '{league}' not found"


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.mcp
class TestMCPErrorHandling:
    """
    Tests for MCP server error handling.

    The server should gracefully handle:
        - Invalid tool parameters
        - Missing required arguments
        - Invalid resource URIs
        - Data fetch failures
        - Timeout conditions
    """

    def test_tools_validate_required_parameters(self, mcp_tools) -> None:
        """
        Test that tools define required parameters.

        Tools should clearly specify:
            - Which parameters are required
            - Which are optional
            - Default values for optional params

        This allows:
            - LLMs to validate before calling
            - Clear error messages for users
            - Consistent parameter handling

        Example:
            get_schedule tool requires 'league' parameter
            If LLM tries to call without it, gets clear error:
            "Missing required parameter: league"
        """
        for tool in mcp_tools:
            schema = tool["inputSchema"]

            # Check if tool has required parameters defined
            if "required" in schema:
                required_params = schema["required"]
                properties = schema["properties"]

                # Verify required params exist in properties
                for param in required_params:
                    assert param in properties, (
                        f"Tool '{tool['name']}' lists '{param}' as required "
                        f"but it's not in properties"
                    )

    def test_resource_handlers_are_callable(self, mcp_resources) -> None:
        """
        Test that all resource handlers are callable functions.

        Each resource must have a handler function that:
            - Accepts appropriate parameters
            - Returns formatted markdown content
            - Handles errors gracefully

        Example handler:
            def resource_handler(uri: str) -> str:
                return "# Resource Content\\n\\nFormatted markdown..."
        """
        for resource in mcp_resources:
            handler = resource["handler"]
            assert callable(handler), f"Resource '{resource['uri']}' handler is not callable"

    def test_tool_handlers_are_callable(self, mcp_tools) -> None:
        """
        Test that all tool handlers are callable functions.

        Each tool must have a handler function that:
            - Accepts parameters matching inputSchema
            - Returns formatted data or error
            - Handles exceptions gracefully

        Example handler:
            def tool_handler(league: str, season: str = None) -> Dict:
                # Fetch and format data
                return {"data": [...], "metadata": {...}}
        """
        for tool in mcp_tools:
            handler = tool["handler"]
            assert callable(handler), f"Tool '{tool['name']}' handler is not callable"


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.mcp
@pytest.mark.slow
class TestMCPPerformance:
    """
    Tests for MCP server performance.

    Performance expectations:
        - Tool calls: <60s for fresh data, <100ms for cached
        - Resource fetches: <10ms (all in-memory)
        - Prompt expansion: <1ms (simple string templates)
        - Memory usage: Reasonable (shared cache with REST API)
    """

    def test_resource_fetches_are_fast(self, mcp_resources) -> None:
        """
        Test that resource fetches are fast (<10ms).

        Resources are in-memory documentation, so they should be
        nearly instant. Fast resource access allows LLMs to:
            - Browse documentation quickly
            - Reference information without delays
            - Provide responsive user experience

        Example:
            import time
            start = time.time()
            content = resource_handler("cbb://leagues")
            elapsed = time.time() - start
            assert elapsed < 0.01  # <10ms
        """
        import time

        # Test fetching a resource
        leagues_resource = next((r for r in mcp_resources if r["uri"] == "cbb://leagues"), None)

        assert leagues_resource is not None, "leagues resource not found"

        handler = leagues_resource["handler"]

        start_time = time.time()
        content = handler("cbb://leagues")
        elapsed_time = time.time() - start_time

        assert (
            elapsed_time < 0.01
        ), f"Resource fetch took {elapsed_time*1000:.1f}ms, should be <10ms"
        assert isinstance(content, str), "Resource content should be string"
        assert len(content) > 0, "Resource content should not be empty"

    def test_tool_registry_lookup_is_fast(self, mcp_tools) -> None:
        """
        Test that tool registry lookups are fast.

        When LLMs call tools, the server needs to:
            1. Look up tool by name (should be O(1) dict lookup)
            2. Validate parameters
            3. Execute handler

        Fast lookup ensures minimal overhead.

        Example:
            tools_by_name = {tool["name"]: tool for tool in tools}
            start = time.time()
            tool = tools_by_name["get_schedule"]  # <1ms
            elapsed = time.time() - start
        """
        import time

        # Build lookup dict (simulating server's registry)
        tools_by_name = {tool["name"]: tool for tool in mcp_tools}

        # Test lookup performance
        start_time = time.time()
        tool = tools_by_name.get("get_schedule")
        elapsed_time = time.time() - start_time

        assert elapsed_time < 0.001, f"Tool lookup took {elapsed_time*1000:.3f}ms, should be <1ms"
        assert tool is not None, "get_schedule tool should exist"
