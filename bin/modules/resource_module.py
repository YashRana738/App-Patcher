"""
Resource patcher module.

Applies find/replace patches to resource XML files
(res/values/strings.xml, colors.xml, etc.)

Each patch file is a JSON object with:
    "target":       Relative path inside decoded APK (e.g. "res/values/strings.xml")
    "replacements": List of {"find": "...", "replace": "..."} objects.
"""

import json
import os
import re
from typing import Any, Dict, List, Tuple

from bin.modules import logger
from bin.modules.exceptions import ResourcePatchError


def apply_resource_patches(
    decoded_dir: str,
    config: Dict[str, Any],
    project_root: str,
    skip_on_fail: bool = True,
) -> List[Dict[str, Any]]:
    """
    Apply all resource patches defined in config.

    Args:
        decoded_dir:  Path to the decoded APK directory.
        config:       Patches config dict.
        project_root: Project root for resolving patch file paths.
        skip_on_fail: If True, skip patches that fail.

    Returns:
        A list of patch result dicts.
    """
    results: List[Dict[str, Any]] = []
    patch_files = config.get("resource_patches", [])

    if not patch_files:
        logger.info("No resource patches configured — skipping")
        return results

    for patch_file_rel in patch_files:
        patch_file = os.path.normpath(
            os.path.join(project_root, patch_file_rel)
        )

        # Load patch file
        if not os.path.isfile(patch_file):
            result = _make_result(patch_file_rel, "skipped", f"Patch file not found: {patch_file}")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", "File not found")
            if not skip_on_fail:
                raise ResourcePatchError(f"Patch file not found: {patch_file}")
            continue

        try:
            with open(patch_file, "r", encoding="utf-8") as pf:
                patch = json.load(pf)
        except json.JSONDecodeError as e:
            result = _make_result(patch_file_rel, "failed", f"Invalid JSON: {e}")
            results.append(result)
            logger.patch_result(patch_file_rel, "failed", f"Invalid JSON: {e}")
            if not skip_on_fail:
                raise ResourcePatchError(f"Invalid JSON in {patch_file}: {e}")
            continue

        # Resolve target file
        target_rel = patch.get("target", "")
        if not target_rel:
            result = _make_result(patch_file_rel, "skipped", "No 'target' specified in patch")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", "No target specified")
            continue

        target_path = os.path.join(decoded_dir, target_rel)

        if not os.path.exists(target_path):
            result = _make_result(patch_file_rel, "skipped", f"Target not found: {target_rel}")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", f"Target not found: {target_rel}")
            if not skip_on_fail:
                raise ResourcePatchError(f"Target not found: {target_path}")
            continue

        target_files: List[str] = []
        if os.path.isdir(target_path):
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith(".xml"):
                        target_files.append(os.path.join(root, f))
        else:
            target_files.append(target_path)

        if not target_files:
            result = _make_result(patch_file_rel, "skipped", f"No XML files found in target dir: {target_rel}")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", "No matching XML files")
            continue

        replacements = patch.get("replacements", [])
        if not replacements:
            result = _make_result(patch_file_rel, "skipped", "No replacements defined")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", "No replacements defined")
            continue

        applied_count = 0
        modified_files_count = 0

        for t_file in target_files:
            try:
                with open(t_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.debug(f"Could not read {t_file}: {e}")
                continue

            orig_content = content
            file_applied = 0

            for rep in replacements:
                find_str = rep.get("find", "")
                replace_str = rep.get("replace", "")
                is_regex = rep.get("regex", False)

                if not find_str:
                    continue

                if is_regex:
                    matches = len(re.findall(find_str, content))
                    if matches > 0:
                        content = re.sub(find_str, replace_str, content)
                        file_applied += matches
                else:
                    matches = content.count(find_str)
                    if matches > 0:
                        content = content.replace(find_str, replace_str)
                        file_applied += matches

            if content != orig_content:
                with open(t_file, "w", encoding="utf-8") as f:
                    f.write(content)
                modified_files_count += 1
                applied_count += file_applied

        if applied_count > 0:
            msg = f"{applied_count} applied across {modified_files_count} modified file(s) ({len(target_files)} scanned)"
            result = _make_result(patch_file_rel, "applied", msg)
            results.append(result)
            logger.patch_result(patch_file_rel, "applied", msg)
        else:
            msg = f"0 replacements matched across {len(target_files)} scanned file(s)"
            result = _make_result(patch_file_rel, "skipped", msg)
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", msg)

    return results


def _make_result(name: str, status: str, message: str) -> Dict[str, Any]:
    """Helper to create a patch result dictionary."""
    return {"name": name, "status": status, "message": message}
