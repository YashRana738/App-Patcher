"""
Structured logging module for APK Porter.

Provides colored console output via colorama and optional file logging.
Log levels: DEBUG, INFO, WARN, SUCCESS, ERROR, FATAL.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional

from colorama import Fore, Style, init

init(autoreset=True)

# Ensure stdout can handle unicode on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # fallback to default encoding

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_file_handler: Optional[logging.FileHandler] = None
_logger: Optional[logging.Logger] = None
_log_level: str = "INFO"

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "FATAL": logging.CRITICAL,
}


def _timestamp() -> str:
    """Return a formatted timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def setup_logging(log_dir: str = "logs", log_level: str = "INFO") -> None:
    """
    Initialise the logging system.

    Creates the log directory if needed, sets up a file handler,
    and stores the desired log level for console filtering.
    """
    global _file_handler, _logger, _log_level

    _log_level = log_level.upper()

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(
        log_dir, f"porter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    _logger = logging.getLogger("apk_porter")
    _logger.setLevel(logging.DEBUG)  # capture everything to file

    # File handler — always captures DEBUG+
    _file_handler = logging.FileHandler(log_file, encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    )
    _logger.addHandler(_file_handler)

    info(f"Log file: {log_file}")


def _should_print(level: str) -> bool:
    """Check whether a message at *level* should be printed to the console."""
    level_order = ["DEBUG", "INFO", "WARN", "SUCCESS", "ERROR", "FATAL"]
    try:
        return level_order.index(level) >= level_order.index(_log_level)
    except ValueError:
        return True


def _write_file(level: str, msg: str) -> None:
    """Write to the file logger if it has been initialised."""
    if _logger is None:
        return
    mapped = _LEVEL_MAP.get(level, logging.INFO)
    _logger.log(mapped, msg)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def debug(msg: str) -> None:
    """Log a DEBUG-level message (grey, only shown when level=DEBUG)."""
    _write_file("DEBUG", msg)
    if _should_print("DEBUG"):
        print(f"{Style.DIM}[{_timestamp()}] [DEBUG] {msg}{Style.RESET_ALL}")


def info(msg: str) -> None:
    """Log an INFO-level message (white)."""
    _write_file("INFO", msg)
    if _should_print("INFO"):
        print(f"[{_timestamp()}] [INFO] {msg}")


def success(msg: str) -> None:
    """Log a SUCCESS message (green)."""
    _write_file("INFO", f"SUCCESS: {msg}")
    if _should_print("SUCCESS"):
        print(f"{Fore.GREEN}[{_timestamp()}] [SUCCESS] {msg}{Style.RESET_ALL}")


def warn(msg: str) -> None:
    """Log a WARNING-level message (yellow)."""
    _write_file("WARN", msg)
    if _should_print("WARN"):
        print(f"{Fore.YELLOW}[{_timestamp()}] [WARN] {msg}{Style.RESET_ALL}")


def error(msg: str) -> None:
    """Log an ERROR-level message (red)."""
    _write_file("ERROR", msg)
    if _should_print("ERROR"):
        print(f"{Fore.RED}[{_timestamp()}] [ERROR] {msg}{Style.RESET_ALL}")


def fatal(msg: str) -> None:
    """Log a FATAL message (bright red) and exit."""
    _write_file("FATAL", msg)
    print(f"{Fore.RED}{Style.BRIGHT}[{_timestamp()}] [FATAL] {msg}{Style.RESET_ALL}")


def section(title: str) -> None:
    """Print a prominent section divider."""
    line = "=" * 60
    _write_file("INFO", f"{'=' * 20} {title} {'=' * 20}")
    if _should_print("INFO"):
        print(f"\n{Fore.CYAN}{line}")
        print(f"  {title}")
        print(f"{line}{Style.RESET_ALL}\n")


def patch_result(name: str, status: str, message: str = "") -> None:
    """
    Log a single patch result in a consistent format.
    status should be one of: 'applied', 'skipped', 'failed'.
    """
    colour = {
        "applied": Fore.GREEN,
        "skipped": Fore.YELLOW,
        "failed": Fore.RED,
    }.get(status, "")

    tag = status.upper()
    detail = f" — {message}" if message else ""
    full_msg = f"[{tag}] {name}{detail}"

    _write_file("INFO" if status == "applied" else "WARN", full_msg)
    if _should_print("INFO"):
        print(f"  {colour}  ► {full_msg}{Style.RESET_ALL}")
