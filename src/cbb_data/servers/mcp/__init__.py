"""
MCP (Model Context Protocol) server components.

Provides LLM-friendly tools, resources, and prompts for accessing
basketball data.
"""

from .tools import TOOLS
from .resources import RESOURCES
from .prompts import PROMPTS

__all__ = ["TOOLS", "RESOURCES", "PROMPTS"]
