"""
Manifest patcher module.

Applies regex-based find/replace patches to AndroidManifest.xml.
Each patch file is a JSON object with "find" and "replace" keys.
Supports both exact string matching and regex patterns.
"""

import os
import re
import json
from typing import Any, Dict, List, Tuple

from bin.modules import logger
from bin.modules.exceptions import ManifestPatchError, ConfigError


def apply_manifest_patches(
    decoded_dir: str,
    config: Dict[str, Any],
    project_root: str,
    skip_on_fail: bool = True,
) -> List[Dict[str, Any]]:
    """
    Apply all manifest patches defined in config.

    Args:
        decoded_dir:  Path to the decoded APK directory.
        config:       Patches config dict (from patches.json).
        project_root: Absolute path to the project root.
        skip_on_fail: If True, skip patches that don't match and continue.

    Returns:
        A list of patch result dicts with keys: name, status, message.

    Raises:
        ManifestPatchError: If a patch fails and skip_on_fail is False.
    """
    results: List[Dict[str, Any]] = []
    patch_files = config.get("manifest_patches", [])

    if not patch_files:
        logger.info("No manifest patches configured — skipping")
        return results

    manifest_path = os.path.join(decoded_dir, "AndroidManifest.xml")

    if not os.path.isfile(manifest_path):
        raise ManifestPatchError(
            f"AndroidManifest.xml not found in: {decoded_dir}"
        )

    # Read manifest content
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content

    for patch_file_rel in patch_files:
        patch_file = os.path.normpath(
            os.path.join(project_root, patch_file_rel)
        )

        # Load patch definition
        if not os.path.isfile(patch_file):
            result = _make_result(patch_file_rel, "skipped", f"Patch file not found: {patch_file}")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", f"File not found: {patch_file}")
            if not skip_on_fail:
                raise ManifestPatchError(f"Patch file not found: {patch_file}")
            continue

        try:
            with open(patch_file, "r", encoding="utf-8") as pf:
                patch = json.load(pf)
        except json.JSONDecodeError as e:
            result = _make_result(patch_file_rel, "failed", f"Invalid JSON: {e}")
            results.append(result)
            logger.patch_result(patch_file_rel, "failed", f"Invalid JSON: {e}")
            if not skip_on_fail:
                raise ManifestPatchError(f"Invalid JSON in {patch_file}: {e}")
            continue

        # Apply patch
        content, patch_result = _apply_single_manifest_patch(
            content, patch, patch_file_rel, skip_on_fail
        )
        results.append(patch_result)

    # Write back if changed
    if content != original_content:
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.debug("AndroidManifest.xml updated")

    return results


def _apply_single_manifest_patch(
    content: str,
    patch: Dict[str, Any],
    patch_name: str,
    skip_on_fail: bool,
) -> Tuple[str, Dict[str, Any]]:
    """
    Apply a single manifest patch to the content string.

    The patch dict should have:
        "find":    The text or regex pattern to search for (optional if 'replacements' is used).
        "replace": The replacement text.
        "regex":   (optional) If true, treat "find" as a regex pattern.
        "flags":   (optional) Regex flags string.
        "replacements": (optional) List of {"find": "...", "replace": "...", "regex": bool} objects.

    Returns:
        (modified_content, result_dict)
    """
    replacements = patch.get("replacements", [])
    if not replacements:
        replacements = [{
            "find": patch.get("find", ""),
            "replace": patch.get("replace", ""),
            "regex": patch.get("regex", False),
            "flags": patch.get("flags", "")
        }]

    name = patch.get("name", patch_name)
    applied_count = 0
    skipped_count = 0
    new_content = content

    for entry in replacements:
        find = entry.get("find", "")
        replace = entry.get("replace", "")
        use_regex = entry.get("regex", False) or patch.get("regex", False)
        flags_str = entry.get("flags", "") or patch.get("flags", "")

        if not find:
            skipped_count += 1
            continue

        if use_regex:
            # Build regex flags
            flags = 0
            if flags_str:
                for flag_name in flags_str.split("|"):
                    flag_name = flag_name.strip().upper()
                    if hasattr(re, flag_name):
                        flags |= getattr(re, flag_name)

            # Check if pattern matches
            if not re.search(find, new_content, flags=flags):
                logger.debug(f"Manifest regex pattern not found: {find[:60]}...")
                skipped_count += 1
                if not skip_on_fail:
                    raise ManifestPatchError(f"Manifest patch '{name}': regex pattern not found: {find[:80]}")
                continue

            new_content = re.sub(find, replace, new_content, flags=flags)
            applied_count += 1

        else:
            # Exact string match
            if find not in new_content:
                logger.debug(f"Manifest pattern not found: {find[:60]}...")
                skipped_count += 1
                if not skip_on_fail:
                    raise ManifestPatchError(f"Manifest patch '{name}': pattern not found: {find[:80]}")
                continue

            new_content = new_content.replace(find, replace)
            applied_count += 1

    status = "applied" if applied_count > 0 else "skipped"
    msg = f"{applied_count} applied, {skipped_count} skipped"
    logger.patch_result(name, status, msg)
    return new_content, _make_result(name, status, msg)


def _make_result(name: str, status: str, message: str = "") -> Dict[str, Any]:
    """Create a standardised patch result dict."""
    return {
        "name": name,
        "type": "manifest",
        "status": status,
        "message": message,
    }
