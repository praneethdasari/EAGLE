"""Application launcher tool enforcing strict allowlisting and safe process execution."""

import os
import subprocess

from pydantic import BaseModel, Field

from eagle.core.config import SecurityConfig
from eagle.core.exceptions import SecurityViolationError
from eagle.core.logging import get_logger
from eagle.tools.base import BaseTool, ToolResult

logger = get_logger("tools.apps")


class LaunchAppArgs(BaseModel):
    """Arguments for launching an application."""

    app_name: str = Field(
        description="Name or alias of the application to launch (e.g., 'notepad', 'calculator')"
    )
    executable: str | None = Field(
        default=None, description="Optional pre-resolved executable name"
    )


class LaunchAppTool(BaseTool):
    """Tool to safely launch approved desktop applications from the security allowlist."""

    name = "launch_app"
    description = (
        "Launch an approved desktop application from the configured application allowlist."
    )
    parameters_schema = LaunchAppArgs
    is_sensitive = False

    def __init__(self, security_config: SecurityConfig | None = None) -> None:
        self.security_config = security_config or SecurityConfig()

    def _resolve_executable(self, app_name: str) -> tuple[str, str]:
        """Validate application against allowlist and return (canonical_name, executable_command).

        Executable paths are strictly resolved from the configured allowlist.

        Raises:
            SecurityViolationError: If app is not permitted in allowlist or has traversal chars.
        """
        allowed = self.security_config.allowed_applications
        target = app_name.strip().lower()

        # Reject path separators and traversal attempts in app_name
        if "/" in target or "\\" in target or ".." in target:
            raise SecurityViolationError(
                f"Invalid application name '{app_name}'. Path traversal characters are forbidden."
            )

        # 1. Direct match on key in allowed_applications
        if target in allowed:
            return target, allowed[target]

        # 2. Match on alias (exact, prefix >= 3 chars, or word in command)
        for alias, exe_path in allowed.items():
            alias_lower = alias.lower()
            if target == alias_lower:
                return alias, exe_path
            if len(target) >= 3 and alias_lower.startswith(target):
                return alias, exe_path
            if alias_lower in target.split():
                return alias, exe_path

        # 3. Disallowed
        raise SecurityViolationError(
            f"Application '{app_name}' is not in the approved applications allowlist.",
            details={"requested": app_name, "allowed_applications": list(allowed.keys())},
        )

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: LaunchAppArgs = validated_args  # type: ignore[assignment]
        app_name = args.app_name.strip()

        try:
            canonical_name, executable = self._resolve_executable(app_name)
        except SecurityViolationError as sec_err:
            logger.warning(
                "Blocked launch attempt for unauthorized app '%s': %s", app_name, sec_err
            )
            return ToolResult(
                success=False,
                error=sec_err.message,
                metadata={"app_name": app_name, "blocked": True},
            )

        # Launch process using argument array (never shell=True to prevent shell injection)
        logger.info(
            "Launching approved application '%s' with executable: %s", canonical_name, executable
        )
        try:
            # On Windows, start process detached so assistant doesn't block
            creationflags = 0
            if os.name == "nt":
                # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

            process = subprocess.Popen(
                [executable],
                creationflags=creationflags,
                close_fds=True,
            )

            logger.info("Application '%s' started with PID %d", canonical_name, process.pid)
            return ToolResult(
                success=True,
                output=f"Application '{canonical_name}' launched successfully.",
                metadata={
                    "app_name": canonical_name,
                    "executable": executable,
                    "pid": process.pid,
                },
            )
        except FileNotFoundError as fnf_err:
            logger.error(
                "Executable '%s' for app '%s' not found: %s", executable, canonical_name, fnf_err
            )
            return ToolResult(
                success=False,
                error=f"Executable '{executable}' could not be located on the system.",
                metadata={"app_name": canonical_name, "executable": executable},
            )
        except PermissionError as perm_err:
            logger.error("OS permission denied launching '%s': %s", executable, perm_err)
            return ToolResult(
                success=False,
                error=f"OS permission denied when attempting to launch '{executable}'.",
                metadata={"app_name": canonical_name, "executable": executable},
            )
        except Exception as exc:
            logger.error("Unexpected error launching '%s': %s", executable, exc, exc_info=True)
            return ToolResult(
                success=False,
                error=f"Failed to launch application '{canonical_name}': {exc}",
                metadata={"app_name": canonical_name, "executable": executable},
            )
