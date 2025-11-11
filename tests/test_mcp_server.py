"""
Tests for MCP Server tools, resources, and prompts.

Basic test examples demonstrating how to test MCP components.
Run with: pytest tests/test_mcp_server.py -v
"""

from cbb_data.servers.mcp.prompts import PROMPTS
from cbb_data.servers.mcp.resources import (
    RESOURCES,
    STATIC_RESOURCES,
    resource_get_dataset_info,
    resource_get_league_info,
    resource_list_datasets,
)
from cbb_data.servers.mcp.tools import (
    TOOLS,
    tool_get_player_game_stats,
    tool_get_player_season_stats,
    tool_get_recent_games,
    tool_get_schedule,
    tool_list_datasets,
)


class TestMCPTools:
    """Tests for MCP tool definitions and handlers."""

    def test_tools_registry_structure(self) -> None:
        """Test that TOOLS registry has correct structure."""
        assert isinstance(TOOLS, list)
        assert len(TOOLS) > 0

        # Check first tool structure
        tool = TOOLS[0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "handler" in tool

        # Check input schema structure
        schema = tool["inputSchema"]
        assert "type" in schema
        assert "properties" in schema

    def test_tool_list_datasets(self) -> None:
        """Test list_datasets tool."""
        result = tool_list_datasets()

        assert isinstance(result, dict)
        assert result["success"] is True
        assert "data" in result

    def test_tool_get_schedule(self) -> None:
        """Test get_schedule tool with valid parameters."""
        result = tool_get_schedule(league="NCAA-MBB", season="2024", limit=5)

        assert isinstance(result, dict)
        # Should either succeed or return error with clear message
        assert "success" in result

        if result["success"]:
            assert "data" in result
            assert isinstance(result["data"], str)  # Formatted for LLM
        else:
            assert "error" in result

    def test_tool_get_player_game_stats(self) -> None:
        """Test get_player_game_stats tool."""
        result = tool_get_player_game_stats(
            league="NCAA-MBB", season="2024", team=["Duke"], limit=5
        )

        assert isinstance(result, dict)
        assert "success" in result

    def test_tool_get_player_season_stats(self) -> None:
        """Test get_player_season_stats tool."""
        result = tool_get_player_season_stats(
            league="NCAA-MBB", season="2024", per_mode="PerGame", limit=10
        )

        assert isinstance(result, dict)
        assert "success" in result

    def test_tool_get_recent_games(self) -> None:
        """Test get_recent_games tool."""
        result = tool_get_recent_games(league="NCAA-MBB", days=2)

        assert isinstance(result, dict)
        assert "success" in result

    def test_tool_with_invalid_league(self) -> None:
        """Test tool with invalid league parameter."""
        result = tool_get_schedule(league="INVALID_LEAGUE", limit=5)

        assert isinstance(result, dict)
        # Should return error
        assert result["success"] is False
        assert "error" in result

    def test_all_tools_have_handlers(self) -> None:
        """Test that all registered tools have callable handlers."""
        for tool in TOOLS:
            assert callable(tool["handler"])


class TestMCPResources:
    """Tests for MCP resource handlers."""

    def test_resources_registry_structure(self) -> None:
        """Test that RESOURCES registry has correct structure."""
        assert isinstance(RESOURCES, list)
        assert len(RESOURCES) > 0

        # Check structure
        resource = RESOURCES[0]
        assert "uri" in resource
        assert "name" in resource
        assert "description" in resource
        assert "mimeType" in resource
        assert "handler" in resource

    def test_static_resources_structure(self) -> None:
        """Test static resources structure."""
        assert isinstance(STATIC_RESOURCES, list)
        assert len(STATIC_RESOURCES) > 0

        resource = STATIC_RESOURCES[0]
        assert "uri" in resource
        assert "name" in resource
        assert "mimeType" in resource

    def test_resource_list_datasets(self) -> None:
        """Test datasets listing resource."""
        result = resource_list_datasets()

        assert isinstance(result, dict)
        assert "uri" in result
        assert result["uri"] == "cbb://datasets/"
        assert "text" in result or "mimeType" in result

    def test_resource_get_dataset_info(self) -> None:
        """Test getting info for a specific dataset."""
        result = resource_get_dataset_info("schedule")

        assert isinstance(result, dict)
        assert "uri" in result
        assert "text" in result
        assert result["uri"] == "cbb://datasets/schedule"

        # Check that text contains useful info
        text = result["text"]
        assert "schedule" in text.lower()

    def test_resource_get_dataset_info_nonexistent(self) -> None:
        """Test getting info for non-existent dataset."""
        result = resource_get_dataset_info("nonexistent_dataset")

        assert isinstance(result, dict)
        assert "text" in result
        assert "not found" in result["text"].lower()

    def test_resource_get_league_info(self) -> None:
        """Test getting league information."""
        for league in ["NCAA-MBB", "NCAA-WBB", "EuroLeague"]:
            result = resource_get_league_info(league)

            assert isinstance(result, dict)
            assert "uri" in result
            assert f"cbb://leagues/{league}" == result["uri"]
            assert "text" in result

            # Check text contains league info
            text = result["text"]
            assert league in text or league.replace("-", " ") in text

    def test_resource_get_league_info_invalid(self) -> None:
        """Test getting info for invalid league."""
        result = resource_get_league_info("INVALID_LEAGUE")

        assert isinstance(result, dict)
        assert "text" in result
        assert "not found" in result["text"].lower()


class TestMCPPrompts:
    """Tests for MCP prompt templates."""

    def test_prompts_registry_structure(self) -> None:
        """Test that PROMPTS registry has correct structure."""
        assert isinstance(PROMPTS, list)
        assert len(PROMPTS) > 0

        # Check structure of first prompt
        prompt = PROMPTS[0]
        assert "name" in prompt
        assert "description" in prompt
        assert "arguments" in prompt
        assert "template" in prompt

        # Check arguments structure
        if prompt["arguments"]:
            arg = prompt["arguments"][0]
            assert "name" in arg
            assert "description" in arg
            assert "required" in arg

    def test_prompt_templates_have_placeholders(self) -> None:
        """Test that prompt templates contain parameter placeholders."""
        for prompt in PROMPTS:
            template = prompt["template"]
            arguments = prompt["arguments"]

            # Check that required arguments appear in template
            for arg in arguments:
                if arg["required"]:
                    arg_name = arg["name"]
                    # Template should reference this argument
                    assert f"{{{arg_name}}}" in template or arg_name in template.lower()

    def test_expected_prompts_exist(self) -> None:
        """Test that expected prompts are registered."""
        prompt_names = [p["name"] for p in PROMPTS]

        expected_prompts = [
            "top-scorers",
            "team-schedule",
            "recent-games",
            "player-game-log",
            "team-standings",
        ]

        for expected in expected_prompts:
            assert expected in prompt_names, f"Prompt '{expected}' not found"

    def test_prompt_argument_types(self) -> None:
        """Test that prompt arguments have proper types."""
        for prompt in PROMPTS:
            for arg in prompt["arguments"]:
                assert isinstance(arg["name"], str)
                assert isinstance(arg["description"], str)
                assert isinstance(arg["required"], bool)


class TestMCPIntegration:
    """Integration tests for MCP components."""

    def test_tool_execution_returns_formatted_data(self) -> None:
        """Test that tool execution returns LLM-friendly formatted data."""
        result = tool_list_datasets()

        if result["success"]:
            # Data should be formatted string (not raw DataFrame)
            assert isinstance(result["data"], str | list | dict)

    def test_resources_cover_all_datasets(self) -> None:
        """Test that we have resources for all datasets."""
        # Get dataset IDs from list_datasets tool
        datasets_result = tool_list_datasets()

        if datasets_result["success"]:
            # Check that we have static resources for major datasets
            resource_uris = [r["uri"] for r in STATIC_RESOURCES]

            expected_dataset_uris = [
                "cbb://datasets/schedule",
                "cbb://datasets/player_game",
                "cbb://datasets/team_game",
                "cbb://datasets/play_by_play",
            ]

            for uri in expected_dataset_uris:
                assert uri in resource_uris

    def test_prompts_reference_valid_tools(self) -> None:
        """Test that prompts reference tools that exist."""
        tool_names = [t["name"] for t in TOOLS]

        for prompt in PROMPTS:
            template = prompt["template"]

            # Check for tool references in template
            # Most prompts should mention at least one tool
            has_tool_reference = any(tool_name in template for tool_name in tool_names)

            # This is a soft check - not all prompts need to mention tools explicitly
            # but most should
            if "Use the" in template or "tool" in template.lower():
                assert (
                    has_tool_reference
                ), f"Prompt '{prompt['name']}' mentions tools but doesn't reference valid ones"


# Run tests with: pytest tests/test_mcp_server.py -v
