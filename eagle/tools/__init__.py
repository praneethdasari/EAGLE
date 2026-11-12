"""EAGLE Tools subsystem package."""

from eagle.tools.apps import LaunchAppArgs, LaunchAppTool
from eagle.tools.base import BaseTool, EmptyParameters, ToolResult
from eagle.tools.files import InspectFileArgs, InspectFileTool, ListFilesArgs, ListFilesTool
from eagle.tools.registry import ToolRegistry
from eagle.tools.system import (
    BrightnessControlArgs,
    BrightnessControlTool,
    SystemInfoArgs,
    SystemInfoTool,
    VolumeControlArgs,
    VolumeControlTool,
)
from eagle.tools.web import OpenWebsiteArgs, OpenWebsiteTool, WebSearchArgs, WebSearchTool

__all__ = [
    # Base abstractions
    "BaseTool",
    "ToolResult",
    "EmptyParameters",
    "ToolRegistry",
    # Applications
    "LaunchAppTool",
    "LaunchAppArgs",
    # Web & search
    "OpenWebsiteTool",
    "OpenWebsiteArgs",
    "WebSearchTool",
    "WebSearchArgs",
    # Files
    "ListFilesTool",
    "ListFilesArgs",
    "InspectFileTool",
    "InspectFileArgs",
    # System info & hardware control
    "SystemInfoTool",
    "SystemInfoArgs",
    "VolumeControlTool",
    "VolumeControlArgs",
    "BrightnessControlTool",
    "BrightnessControlArgs",
]
