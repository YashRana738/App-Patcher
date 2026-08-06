"""
Build module — repacks a decoded APK directory back into an APK using apktool.
"""

import os
from typing import Dict

from bin.modules import logger
from bin.modules.config_loader import resolve_tool_path
from bin.modules.exceptions import BuildError
from bin.modules.shell import run_command


def build_apk(
    decoded_dir: str,
    output_apk: str,
    tools: Dict[str, str],
    project_root: str,
    use_aapt2: bool = True,
) -> str:
    """
    Repack a decoded APK directory into an unsigned APK.

    Args:
        decoded_dir:  Path to the decoded APK directory.
        output_apk:   Desired path for the output APK.
        tools:        Tool paths dict from tools.json.
        project_root: Absolute path to the project root.
        use_aapt2:    Whether to use --use-aapt2 flag.

    Returns:
        The absolute path to the built (unsigned) APK.

    Raises:
        BuildError: If apktool build fails.
    """
    java = resolve_tool_path("java", tools["java"], project_root)
    apktool = resolve_tool_path("apktool", tools["apktool"], project_root)

    output_dir = os.path.dirname(output_apk)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if os.path.isfile(output_apk):
        try:
            os.remove(output_apk)
        except OSError as e:
            logger.debug(f"Could not remove existing output file {output_apk}: {e}")

    logger.info("Building APK...")

    cmd = [
        java,
        "-jar",
        apktool,
        "b",
        decoded_dir,
        "-o",
        output_apk,
    ]

    if use_aapt2:
        cmd.append("--use-aapt2")

    try:
        run_command(cmd, description="apktool build")
    except Exception as e:
        raise BuildError(f"Failed to build APK: {e}")

    if not os.path.isfile(output_apk):
        raise BuildError(f"Build completed but output APK not found: {output_apk}")

    size_mb = os.path.getsize(output_apk) / (1024 * 1024)
    logger.success(f"APK built: {output_apk} ({size_mb:.1f} MB)")
    return output_apk
