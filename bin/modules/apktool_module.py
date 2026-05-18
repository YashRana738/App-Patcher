"""
APKTool module — decodes (unpacks) an APK using apktool.

Usage:
    decode_apk(apk_path, output_dir, tools, project_root)
"""

import os
import shutil
from typing import Dict

from bin.modules import logger
from bin.modules.shell import run_command
from bin.modules.exceptions import DecodeError


def decode_apk(
    apk_path: str,
    output_dir: str,
    tools: Dict[str, str],
    project_root: str,
) -> str:
    """
    Decode (unpack) an APK using apktool.

    Args:
        apk_path:     Absolute path to the input .apk file.
        output_dir:   Directory where the decoded APK will be written.
        tools:        Tool paths dict from tools.json.
        project_root: Absolute path to the project root.

    Returns:
        The absolute path to the decoded output directory.

    Raises:
        DecodeError: If the APK file doesn't exist or apktool fails.
    """
    if not os.path.isfile(apk_path):
        raise DecodeError(f"Input APK not found: {apk_path}")

    # Resolve tool paths
    java = os.path.join(project_root, tools["java"])
    apktool = os.path.join(project_root, tools["apktool"])

    # Clean previous decode
    if os.path.isdir(output_dir):
        logger.debug(f"Removing previous decode: {output_dir}")
        shutil.rmtree(output_dir, ignore_errors=True)

    logger.info(f"Decoding APK: {os.path.basename(apk_path)}")

    cmd = [
        java,
        "-jar",
        apktool,
        "d",
        "-f",              # force overwrite
        apk_path,
        "-o",
        output_dir,
    ]

    try:
        run_command(cmd, description="apktool decode")
    except Exception as e:
        raise DecodeError(f"Failed to decode APK: {e}")

    # Validate decoded structure
    manifest = os.path.join(output_dir, "AndroidManifest.xml")
    if not os.path.isfile(manifest):
        raise DecodeError(
            f"Decoded APK is missing AndroidManifest.xml — "
            f"apktool may have failed silently."
        )

    logger.success(f"APK decoded to: {output_dir}")
    return output_dir
