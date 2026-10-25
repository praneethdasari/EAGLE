"""System telemetry and safe information reporting tool for EAGLE."""

import platform
from typing import Any

from pydantic import BaseModel, Field

from eagle.core.logging import get_logger
from eagle.tools.base import BaseTool, ToolResult

logger = get_logger("tools.system")


class SystemInfoArgs(BaseModel):
    """Arguments for querying system telemetry."""

    topic: str = Field(
        default="all",
        description="Telemetry topic to query: 'all', 'platform', 'cpu', 'memory', 'battery'",
    )


class SystemInfoTool(BaseTool):
    """Tool to read safe telemetry metrics (platform, CPU, RAM, battery) without system modification."""

    name = "system_info"
    description = "Read operating system, CPU, memory, and battery status metrics."
    parameters_schema = SystemInfoArgs
    is_sensitive = False

    def _get_platform_info(self) -> dict[str, Any]:
        return {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor() or "Unknown",
            "python_version": platform.python_version(),
        }

    def _get_cpu_info(self) -> dict[str, Any]:
        try:
            import psutil

            cpu_usage = psutil.cpu_percent(interval=None)
            logical_cores = psutil.cpu_count(logical=True)
            physical_cores = psutil.cpu_count(logical=False)
            return {
                "usage_percent": cpu_usage,
                "logical_cores": logical_cores or 1,
                "physical_cores": physical_cores or 1,
            }
        except Exception as exc:
            logger.warning("Could not query CPU metrics via psutil: %s", exc)
            return {"usage_percent": "N/A", "cores": "N/A"}

    def _get_memory_info(self) -> dict[str, Any]:
        try:
            import psutil

            vm = psutil.virtual_memory()
            total_gb = vm.total / (1024**3)
            available_gb = vm.available / (1024**3)
            used_gb = vm.used / (1024**3)
            return {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "available_gb": round(available_gb, 2),
                "percent_used": vm.percent,
            }
        except Exception as exc:
            logger.warning("Could not query memory metrics via psutil: %s", exc)
            return {"error": "Memory metrics unavailable"}

    def _get_battery_info(self) -> dict[str, Any]:
        try:
            import psutil

            battery = psutil.sensors_battery()
            if battery is None:
                return {
                    "has_battery": False,
                    "status": "No battery detected (Desktop / AC powered)",
                }

            secs_left = battery.secsleft
            time_left_str = "Calculating / Plugged in"
            if (
                secs_left not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN)
                and secs_left > 0
            ):
                hours = int(secs_left // 3600)
                minutes = int((secs_left % 3600) // 60)
                time_left_str = f"{hours}h {minutes}m remaining"

            return {
                "has_battery": True,
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "time_left": time_left_str,
            }
        except Exception as exc:
            logger.warning("Could not query battery sensor: %s", exc)
            return {
                "has_battery": False,
                "status": "Battery sensors unavailable",
            }

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: SystemInfoArgs = validated_args  # type: ignore[assignment]
        topic = args.topic.strip().lower()

        logger.info("Gathering system information for topic: '%s'", topic)

        platform_info = self._get_platform_info()
        cpu_info = self._get_cpu_info()
        mem_info = self._get_memory_info()
        battery_info = self._get_battery_info()

        metadata: dict[str, Any] = {
            "platform": platform_info,
            "cpu": cpu_info,
            "memory": mem_info,
            "battery": battery_info,
        }

        if topic == "battery":
            if battery_info.get("has_battery"):
                plugged_str = "Plugged in" if battery_info.get("power_plugged") else "On battery"
                output_text = f"Battery: {battery_info['percent']}% ({plugged_str}, {battery_info['time_left']})"
            else:
                output_text = f"Battery: {battery_info.get('status', 'No battery detected')}"
            return ToolResult(success=True, output=output_text, metadata=metadata)

        if topic == "cpu":
            output_text = (
                f"CPU: {cpu_info.get('usage_percent', 'N/A')}% utilization "
                f"({cpu_info.get('logical_cores', 'N/A')} logical cores)"
            )
            return ToolResult(success=True, output=output_text, metadata=metadata)

        if topic in ("memory", "ram"):
            if "percent_used" in mem_info:
                output_text = (
                    f"Memory: {mem_info['used_gb']} GB / {mem_info['total_gb']} GB "
                    f"({mem_info['percent_used']}% used)"
                )
            else:
                output_text = "Memory: Telemetry unavailable"
            return ToolResult(success=True, output=output_text, metadata=metadata)

        if topic in ("platform", "os"):
            output_text = (
                f"OS: {platform_info['os']} {platform_info['release']} "
                f"({platform_info['architecture']}), Python {platform_info['python_version']}"
            )
            return ToolResult(success=True, output=output_text, metadata=metadata)

        # Default: Full telemetry overview (topic == 'all' or 'system')
        lines = ["=== EAGLE System Telemetry ==="]
        lines.append(
            f"OS: {platform_info['os']} {platform_info['release']} ({platform_info['architecture']})"
        )
        lines.append(
            f"CPU: {cpu_info.get('usage_percent', 'N/A')}% utilization ({cpu_info.get('logical_cores', 'N/A')} cores)"
        )

        if "percent_used" in mem_info:
            lines.append(
                f"Memory: {mem_info['used_gb']} GB / {mem_info['total_gb']} GB ({mem_info['percent_used']}%)"
            )
        else:
            lines.append("Memory: Unavailable")

        if battery_info.get("has_battery"):
            plugged_str = "Plugged in" if battery_info.get("power_plugged") else "On battery"
            lines.append(
                f"Battery: {battery_info['percent']}% ({plugged_str}, {battery_info['time_left']})"
            )
        else:
            lines.append(f"Battery: {battery_info.get('status', 'No battery')}")

        output_text = "\n".join(lines)
        return ToolResult(
            success=True,
            output=output_text,
            metadata=metadata,
        )
