"""Main entry point for EAGLE (Enhanced Autonomous General-purpose Local Executive)."""

import argparse
import sys

from eagle import __app_name__, __description__, __version__
from eagle.core.config import load_config
from eagle.core.events import (
    EventBus,
    SpeechOutputRequestedEvent,
    ToolExecutionRequestedEvent,
)
from eagle.core.logging import get_logger, setup_logging
from eagle.services.command_router import CommandIntent, CommandRouter
from eagle.tools.registry import ToolRegistry

BANNER = f"""
====================================================================
  ____   _     ____   _      _____
 |  __| / \\   / ___| | |    | ____|
 | |_  / _ \\ | |  _  | |    |  _|
 |  _|/ ___ \\| |_| | | |___ | |___
 |_| /_/   \\_\\\\____| |_____||_____|

 {__app_name__} — {__description__}
 Version: {__version__}
====================================================================
"""


def parse_arguments(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="eagle",
        description=f"{__app_name__}: {__description__}",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"{__app_name__} v{__version__}"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to custom config.json file")
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override logging level",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in command-line text interface mode (no GUI)",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Application main execution lifecycle."""
    parsed = parse_arguments(args)

    # 1. Load configuration
    try:
        config = load_config(parsed.config)
    except Exception as exc:
        print(f"Error loading configuration: {exc}", file=sys.stderr)
        return 1

    # 2. Setup logging
    log_level = parsed.log_level or config.log_level
    setup_logging(level=log_level)
    logger = get_logger("main")

    logger.info("Starting %s v%s ...", __app_name__, __version__)
    print(BANNER)
    print(f"Loaded configuration for {config.app_name}. Log level: {log_level}")

    # 3. Initialize EventBus, ToolRegistry, and CommandRouter
    event_bus = EventBus()
    tool_registry = ToolRegistry(
        confirm_sensitive_actions=config.security.confirm_sensitive_actions
    )
    router = CommandRouter(config=config, tool_registry=tool_registry, event_bus=event_bus)

    # Wire event feedback
    def on_speech_output(evt: SpeechOutputRequestedEvent) -> None:
        print(f"\n[EAGLE Spoken]: {evt.text}")

    def on_tool_request(evt: ToolExecutionRequestedEvent) -> None:
        print(f"[EAGLE Tool Request]: {evt.tool_name} with {evt.arguments}")

    event_bus.subscribe(SpeechOutputRequestedEvent, on_speech_output)
    event_bus.subscribe(ToolExecutionRequestedEvent, on_tool_request)

    if parsed.cli:
        print("Running in CLI mode. Type 'quit' or 'exit' to stop.")
        try:
            while True:
                user_input = input("\nEAGLE> ").strip()
                if not user_input:
                    continue
                route = router.route(user_input)
                print(f"[Routed Intent]: {route.intent.value} | Matched: {route.matched_rule}")
                router.dispatch(route)

                if route.intent == CommandIntent.SYSTEM_CONTROL and route.action_name in (
                    "exit",
                    "quit",
                    "goodbye",
                ):
                    print("Shutting down EAGLE. Goodbye!")
                    break
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down EAGLE. Goodbye!")
            return 0
    else:
        print("GUI mode selected. (Use --cli for interactive terminal mode).")
        logger.info("EAGLE foundation initialized successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
