"""EAGLE Core subsystem package."""

from eagle.core.config import EagleConfig, load_config
from eagle.core.events import Event, EventBus
from eagle.core.exceptions import (
    AudioError,
    ConfigurationError,
    EagleError,
    OfflinePolicyViolationError,
    SecurityViolationError,
    ToolError,
)
from eagle.core.logging import get_logger, setup_logging
from eagle.core.paths import (
    get_app_root,
    get_default_config_path,
    get_logs_dir,
    get_models_dir,
    get_user_data_dir,
    is_frozen,
)

__all__ = [
    "EagleConfig",
    "load_config",
    "Event",
    "EventBus",
    "EagleError",
    "ConfigurationError",
    "AudioError",
    "ToolError",
    "SecurityViolationError",
    "OfflinePolicyViolationError",
    "get_logger",
    "setup_logging",
    "is_frozen",
    "get_app_root",
    "get_default_config_path",
    "get_user_data_dir",
    "get_logs_dir",
    "get_models_dir",
]
