"""
Config loader for APK Porter.

Loads and validates JSON/YAML configuration files.
Resolves relative paths against the project root.
"""

import json
import os
from typing import Any, Dict, List

from bin.modules import logger
from bin.modules.exceptions import ConfigError


def load_json(path: str) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents as a dictionary.

    Raises:
        ConfigError: If the file is missing or contains invalid JSON.
    """
    if not os.path.isfile(path):
        raise ConfigError(f"Config file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {path}: {e}")

    logger.debug(f"Loaded config: {path}")
    return data


def load_patch_file(path: str) -> Dict[str, Any]:
    """
    Load a single patch definition file (JSON).

    Raises:
        ConfigError: If the file is missing or contains invalid JSON.
    """
    if not os.path.isfile(path):
        raise ConfigError(f"Patch file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in patch file {path}: {e}")

    return data


def validate_tools(tools: Dict[str, str], project_root: str) -> None:
    """
    Verify that every tool referenced in tools.json actually exists on disk.

    Raises:
        ConfigError: If any required tool is missing.
    """
    missing: List[str] = []
    for name, rel_path in tools.items():
        abs_path = os.path.join(project_root, rel_path)
        if not os.path.exists(abs_path):
            missing.append(f"  {name}: {abs_path}")

    if missing:
        raise ConfigError(
            "Missing tools:\n" + "\n".join(missing)
        )

    logger.debug("All tools validated OK")


def validate_patches_config(patches: Dict[str, Any]) -> None:
    """
    Basic structural validation of patches.json.

    Checks that expected keys exist and patch file lists are arrays.
    Does NOT validate the contents of each individual patch file.
    """
    expected_keys = [
        "manifest_patches",
        "resource_patches",
        "smali_patches",
        "inject_dirs",
    ]

    for key in expected_keys:
        if key not in patches:
            logger.warn(f"Missing key '{key}' in patches config — defaulting to empty list")
            patches[key] = []

        if not isinstance(patches[key], list):
            raise ConfigError(f"patches.json: '{key}' must be a list, got {type(patches[key]).__name__}")

    logger.debug("Patches config validated OK")


def resolve_path(rel_path: str, project_root: str) -> str:
    """Resolve a relative path against the project root."""
    return os.path.normpath(os.path.join(project_root, rel_path))
