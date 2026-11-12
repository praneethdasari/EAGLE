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


class VolumeControlArgs(BaseModel):
    """Arguments for controlling master system audio volume."""

    action: str = Field(
        default="get",
        description="Volume action: 'get', 'set', 'increase', 'decrease', 'mute', 'unmute'",
    )
    level: float | None = Field(
        default=None,
        description="Target volume level as a percentage (0-100) or step amount",
    )


class VolumeControlTool(BaseTool):
    """Tool to adjust and query Windows master audio volume."""

    name = "volume_control"
    description = (
        "Control or query master system volume: get volume, set volume level (0-100), "
        "increase, decrease, mute, or unmute."
    )
    parameters_schema = VolumeControlArgs
    is_sensitive = False

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: VolumeControlArgs = validated_args  # type: ignore[assignment]
        action = args.action.strip().lower()

        try:
            import pythoncom  # type: ignore[import-untyped]

            pythoncom.CoInitialize()
        except Exception:
            pass

        try:
            import pycaw.pycaw as pycaw  # type: ignore[import-untyped]

            speakers = pycaw.AudioUtilities.GetSpeakers()
            if not speakers or not hasattr(speakers, "EndpointVolume"):
                return ToolResult(
                    success=False,
                    output="Audio output endpoint is not available.",
                    error="No active speaker device found.",
                )

            volume_endpoint = speakers.EndpointVolume

            if action == "get":
                scalar = float(volume_endpoint.GetMasterVolumeLevelScalar())
                percent = round(scalar * 100)
                is_muted = bool(volume_endpoint.GetMute())
                muted_str = " (muted)" if is_muted else ""
                return ToolResult(
                    success=True,
                    output=f"Master volume is {percent}%{muted_str}.",
                    metadata={"volume": percent, "muted": is_muted},
                )

            if action == "mute":
                volume_endpoint.SetMute(1, None)
                return ToolResult(
                    success=True,
                    output="Master audio muted.",
                    metadata={"muted": True},
                )

            if action == "unmute":
                volume_endpoint.SetMute(0, None)
                scalar = float(volume_endpoint.GetMasterVolumeLevelScalar())
                percent = round(scalar * 100)
                return ToolResult(
                    success=True,
                    output=f"Master audio unmuted. Volume is {percent}%.",
                    metadata={"volume": percent, "muted": False},
                )

            if action == "set":
                target_percent = 50.0 if args.level is None else float(args.level)
                target_percent = max(0.0, min(100.0, target_percent))
                scalar = target_percent / 100.0
                volume_endpoint.SetMasterVolumeLevelScalar(scalar, None)
                if volume_endpoint.GetMute():
                    volume_endpoint.SetMute(0, None)
                return ToolResult(
                    success=True,
                    output=f"Master volume set to {round(target_percent)}%.",
                    metadata={"volume": round(target_percent), "muted": False},
                )

            if action == "increase":
                step = float(args.level) if args.level is not None else 10.0
                current_scalar = float(volume_endpoint.GetMasterVolumeLevelScalar())
                new_percent = min(100.0, (current_scalar * 100.0) + step)
                volume_endpoint.SetMasterVolumeLevelScalar(new_percent / 100.0, None)
                if volume_endpoint.GetMute():
                    volume_endpoint.SetMute(0, None)
                return ToolResult(
                    success=True,
                    output=f"Master volume increased to {round(new_percent)}%.",
                    metadata={"volume": round(new_percent), "muted": False},
                )

            if action == "decrease":
                step = float(args.level) if args.level is not None else 10.0
                current_scalar = float(volume_endpoint.GetMasterVolumeLevelScalar())
                new_percent = max(0.0, (current_scalar * 100.0) - step)
                volume_endpoint.SetMasterVolumeLevelScalar(new_percent / 100.0, None)
                return ToolResult(
                    success=True,
                    output=f"Master volume decreased to {round(new_percent)}%.",
                    metadata={"volume": round(new_percent), "muted": False},
                )

            return ToolResult(
                success=False,
                output=f"Unknown volume action: '{action}'.",
                error=f"Action '{action}' not recognized.",
            )

        except Exception as exc:
            logger.error("Volume control failed: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                output=f"Failed adjusting volume: {exc}",
                error=str(exc),
            )
        finally:
            try:
                import pythoncom  # type: ignore[import-untyped]

                pythoncom.CoUninitialize()
            except Exception:
                pass


class BrightnessControlArgs(BaseModel):
    """Arguments for controlling display brightness."""

    action: str = Field(
        default="get",
        description="Brightness action: 'get', 'set', 'increase', 'decrease', 'max', 'min'",
    )
    level: float | None = Field(
        default=None,
        description="Target brightness level as a percentage (0-100) or step amount",
    )


class BrightnessControlTool(BaseTool):
    """Tool to adjust and query display brightness."""

    name = "brightness_control"
    description = (
        "Control or query display brightness: get brightness, set brightness level (0-100), "
        "increase, decrease, or set to max/min."
    )
    parameters_schema = BrightnessControlArgs
    is_sensitive = False

    def _get_current_brightness(self) -> int:
        import screen_brightness_control as sbc  # type: ignore[import-untyped]

        levels = sbc.get_brightness()
        if isinstance(levels, list) and levels:
            return int(levels[0])
        elif isinstance(levels, (int, float)):
            return int(levels)
        raise RuntimeError("No active display detected for brightness control.")

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: BrightnessControlArgs = validated_args  # type: ignore[assignment]
        action = args.action.strip().lower()

        try:
            import screen_brightness_control as sbc  # type: ignore[import-untyped]

            if action == "get":
                current = self._get_current_brightness()
                return ToolResult(
                    success=True,
                    output=f"Display brightness is {current}%.",
                    metadata={"brightness": current},
                )

            if action == "set":
                target = 50 if args.level is None else int(round(args.level))
                target = max(0, min(100, target))
                sbc.set_brightness(target)
                return ToolResult(
                    success=True,
                    output=f"Display brightness set to {target}%.",
                    metadata={"brightness": target},
                )

            if action == "increase":
                step = int(round(args.level)) if args.level is not None else 10
                current = self._get_current_brightness()
                new_val = min(100, current + step)
                sbc.set_brightness(new_val)
                return ToolResult(
                    success=True,
                    output=f"Display brightness increased to {new_val}%.",
                    metadata={"brightness": new_val},
                )

            if action == "decrease":
                step = int(round(args.level)) if args.level is not None else 10
                current = self._get_current_brightness()
                new_val = max(0, current - step)
                sbc.set_brightness(new_val)
                return ToolResult(
                    success=True,
                    output=f"Display brightness decreased to {new_val}%.",
                    metadata={"brightness": new_val},
                )

            if action == "max":
                sbc.set_brightness(100)
                return ToolResult(
                    success=True,
                    output="Display brightness set to maximum (100%).",
                    metadata={"brightness": 100},
                )

            if action == "min":
                sbc.set_brightness(0)
                return ToolResult(
                    success=True,
                    output="Display brightness set to minimum (0%).",
                    metadata={"brightness": 0},
                )

            return ToolResult(
                success=False,
                output=f"Unknown brightness action: '{action}'.",
                error=f"Action '{action}' not recognized.",
            )

        except Exception as exc:
            logger.warning("Brightness control failed: %s", exc)
            return ToolResult(
                success=False,
                output=(
                    f"Display brightness could not be adjusted: {exc}. "
                    "Note: External monitors or sandbox isolation may restrict hardware backlight controls."
                ),
                error=str(exc),
            )
