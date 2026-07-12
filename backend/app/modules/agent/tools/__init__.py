"""Authoritative production Tool contracts for the WeChat Agent."""

from .registry import ToolDefinition, ToolRegistry
from .result import ToolResult

__all__ = ["ToolDefinition", "ToolRegistry", "ToolResult"]
