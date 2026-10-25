"""Sandboxed filesystem tools enforcing strict directory containment and path safety."""

import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from eagle.core.config import SecurityConfig, is_path_within_allowed
from eagle.core.exceptions import SecurityViolationError
from eagle.core.logging import get_logger
from eagle.tools.base import BaseTool, ToolResult

logger = get_logger("tools.files")


def format_size_bytes(size_bytes: int) -> str:
    """Format byte size into human readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class ListFilesArgs(BaseModel):
    """Arguments for listing files in an authorized directory."""

    directory: str | None = Field(
        default=None,
        description="Directory path to inspect (must be inside configured allowed directories)",
    )
    max_entries: int = Field(default=50, ge=1, le=500, description="Max entries to return")


class ListFilesTool(BaseTool):
    """Tool to inspect and list files in explicitly authorized directories."""

    name = "list_files"
    description = "List files and directories inside an approved allowed directory."
    parameters_schema = ListFilesArgs
    is_sensitive = False

    def __init__(self, security_config: SecurityConfig | None = None) -> None:
        self.security_config = security_config or SecurityConfig()

    def _resolve_target_dir(self, raw_dir: str | None) -> Path:
        """Resolve and validate that target directory is within allowed directories.

        Raises:
            SecurityViolationError: If path attempts to escape allowed directory boundaries.
        """
        allowed = self.security_config.allowed_directories
        if not allowed:
            raise SecurityViolationError(
                "No allowed directories are configured in security settings."
            )

        if not raw_dir or not raw_dir.strip():
            # Default to first allowed directory
            return Path(allowed[0]).resolve()

        resolved = Path(raw_dir.strip()).resolve()

        if not is_path_within_allowed(resolved, allowed):
            raise SecurityViolationError(
                f"Path traversal blocked: '{raw_dir}' is outside permitted directories.",
                details={"requested_path": str(resolved), "allowed_directories": allowed},
            )

        return resolved

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: ListFilesArgs = validated_args  # type: ignore[assignment]
        raw_dir = args.directory

        try:
            target_dir = self._resolve_target_dir(raw_dir)
        except SecurityViolationError as sec_err:
            logger.warning("Blocked file listing attempt outside boundaries: %s", sec_err)
            return ToolResult(
                success=False,
                error=sec_err.message,
                metadata={"blocked": True},
            )

        if not target_dir.exists():
            return ToolResult(
                success=False,
                error=f"Directory '{target_dir}' does not exist.",
                metadata={"directory": str(target_dir)},
            )

        if not target_dir.is_dir():
            return ToolResult(
                success=False,
                error=f"Path '{target_dir}' is a file, not a directory.",
                metadata={"directory": str(target_dir)},
            )

        try:
            entries: list[dict[str, Any]] = []
            for item in sorted(target_dir.iterdir()):
                if len(entries) >= args.max_entries:
                    break

                try:
                    stat = item.stat()
                    mod_dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
                    is_dir = item.is_dir()
                    entries.append(
                        {
                            "name": item.name,
                            "is_dir": is_dir,
                            "size_bytes": 0 if is_dir else stat.st_size,
                            "size_formatted": "<DIR>"
                            if is_dir
                            else format_size_bytes(stat.st_size),
                            "modified": mod_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        }
                    )
                except (OSError, PermissionError):
                    entries.append(
                        {
                            "name": item.name,
                            "is_dir": item.is_dir() if hasattr(item, "is_dir") else False,
                            "size_bytes": 0,
                            "size_formatted": "N/A",
                            "modified": "Inaccessible",
                        }
                    )

            # Format human-readable summary
            lines = [f"Contents of {target_dir} ({len(entries)} items):"]
            for e in entries:
                lines.append(f" - [{e['size_formatted']}] {e['name']} ({e['modified']})")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={
                    "directory": str(target_dir),
                    "count": len(entries),
                    "entries": entries,
                },
            )
        except PermissionError as perm_err:
            logger.error("Permission denied listing %s: %s", target_dir, perm_err)
            return ToolResult(
                success=False,
                error=f"Permission denied accessing directory '{target_dir}'.",
                metadata={"directory": str(target_dir)},
            )
        except Exception as exc:
            logger.error("Error reading directory %s: %s", target_dir, exc)
            return ToolResult(
                success=False,
                error=f"Failed to list directory contents: {exc}",
                metadata={"directory": str(target_dir)},
            )


class InspectFileArgs(BaseModel):
    """Arguments for inspecting metadata of a permitted file."""

    path: str = Field(
        description="Path to the file to inspect (must be inside allowed directories)"
    )


class InspectFileTool(BaseTool):
    """Tool to inspect metadata and properties of a file without destructive actions."""

    name = "inspect_file"
    description = "Inspect file metadata (size, created, modified, type) in permitted directories."
    parameters_schema = InspectFileArgs
    is_sensitive = False

    def __init__(self, security_config: SecurityConfig | None = None) -> None:
        self.security_config = security_config or SecurityConfig()

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: InspectFileArgs = validated_args  # type: ignore[assignment]
        raw_path = args.path.strip()

        allowed = self.security_config.allowed_directories
        resolved = Path(raw_path).resolve()

        if not is_path_within_allowed(resolved, allowed):
            logger.warning("Blocked file inspection outside allowed directories: %s", raw_path)
            return ToolResult(
                success=False,
                error=f"Path traversal blocked: '{raw_path}' is outside permitted directories.",
                metadata={"path": str(resolved), "blocked": True},
            )

        if not resolved.exists():
            return ToolResult(
                success=False,
                error=f"File '{raw_path}' does not exist.",
                metadata={"path": str(resolved)},
            )

        try:
            stat = resolved.stat()
            mod_dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
            created_dt = datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.UTC)
            is_file = resolved.is_file()
            is_dir = resolved.is_dir()
            is_symlink = resolved.is_symlink()

            metadata = {
                "path": str(resolved),
                "name": resolved.name,
                "extension": resolved.suffix.lower() if is_file else "",
                "is_file": is_file,
                "is_dir": is_dir,
                "is_symlink": is_symlink,
                "size_bytes": stat.st_size if is_file else 0,
                "size_formatted": format_size_bytes(stat.st_size) if is_file else "<DIR>",
                "modified": mod_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "created": created_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            }

            output = (
                f"File: {resolved.name}\n"
                f"Path: {resolved}\n"
                f"Type: {'Directory' if is_dir else 'File' + (' (' + resolved.suffix + ')' if resolved.suffix else '')}\n"
                f"Size: {metadata['size_formatted']}\n"
                f"Modified: {metadata['modified']}\n"
                f"Created: {metadata['created']}"
            )

            return ToolResult(
                success=True,
                output=output,
                metadata=metadata,
            )
        except PermissionError as perm_err:
            logger.error("Permission denied inspecting %s: %s", resolved, perm_err)
            return ToolResult(
                success=False,
                error=f"Permission denied accessing '{resolved}'.",
                metadata={"path": str(resolved)},
            )
        except Exception as exc:
            logger.error("Error inspecting %s: %s", resolved, exc)
            return ToolResult(
                success=False,
                error=f"Failed to inspect file '{resolved}': {exc}",
                metadata={"path": str(resolved)},
            )
