"""
Subprocess wrapper for APK Porter.

Provides a single `run_command` function that:
  - Logs the command being run
  - Captures stdout/stderr
  - Raises ToolError on non-zero exit
  - Supports optional timeout
"""

import subprocess
from typing import List, Optional

from bin.modules import logger
from bin.modules.exceptions import ToolError


def run_command(
    cmd: List[str],
    description: str = "",
    timeout: Optional[int] = 600,
    cwd: Optional[str] = None,
) -> str:
    """
    Execute a shell command and return its combined stdout.

    Args:
        cmd:         Command + arguments as a list of strings.
        description: Human-readable label for log output.
        timeout:     Seconds before the process is killed (default 600).
        cwd:         Working directory for the subprocess.

    Returns:
        The captured stdout as a string.

    Raises:
        ToolError: If the command exits with a non-zero return code.
    """
    label = description or " ".join(cmd[:3])
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise ToolError(f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise ToolError(f"Command timed out after {timeout}s: {label}")

    if result.stdout and result.stdout.strip():
        logger.debug(f"Output ({label}):\n{result.stdout.strip()}")

    if result.returncode != 0:
        raise ToolError(
            f"Command failed (exit {result.returncode}): {label}\n"
            f"Output:\n{result.stdout}"
        )

    return result.stdout
