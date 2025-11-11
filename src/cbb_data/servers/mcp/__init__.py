"""
MCP (Model Context Protocol) server components.

Provides LLM-friendly tools, resources, and prompts for accessing
basketball data.
"""

from .prompts import PROMPTS
from .resources import RESOURCES
from .tools import TOOLS

__all__ = ["TOOLS", "RESOURCES", "PROMPTS"]
