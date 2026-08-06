"""
Resource patcher module.

Applies find/replace patches to resource XML files
(res/values/strings.xml, colors.xml, etc.)

Each patch file is a JSON object with:
    "target":       Relative path inside decoded APK (e.g. "res/values/strings.xml")
    "replacements": List of {"find": "...", "replace": "..."} objects.
"""

import os
import re
import json
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
            logger.patch_result(patch_file_rel, "skipped", f"File not found")
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

        target_path = os.path.join(decoded_dir, target_rel)

        if not os.path.exists(target_path):
            result = _make_result(patch_file_rel, "skipped", f"Target not found: {target_rel}")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", f"Target not found: {target_rel}")
            if not skip_on_fail:
                raise ResourcePatchError(f"Target not found: {target_path}")
            continue

        target_files = []
        if os.path.isdir(target_path):
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith(".xml"):
                        target_files.append(os.path.join(root, f))
        else:
            target_files.append(target_path)

        if not target_files:
            result = _make_result(patch_file_rel, "skipped", f"No XML files found in target: {target_rel}")
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", f"No XML files found: {target_rel}")
            continue

        # Regex mode can be set at patch level or per-entry level
        patch_regex     = patch.get("regex", False)
        patch_flags_str = patch.get("flags", "MULTILINE")

        replacements = patch.get("replacements", [])
        overall_applied = 0
        overall_skipped = 0
        modified_files = set()

        for entry in replacements:
            find      = entry.get("find", "")
            replace   = entry.get("replace", "")
            use_regex = entry.get("regex", patch_regex)
            flags_str = entry.get("flags", patch_flags_str)

            if not find:
                overall_skipped += 1
                continue

            # Compile regex flags
            re_flags = 0
            if use_regex:
                for flag_name in flags_str.replace(" ", "").split("|"):
                    flag_name = flag_name.strip()
                    if flag_name and hasattr(re, flag_name):
                        re_flags |= getattr(re, flag_name)

            replacement_applied = False

            for t_file in target_files:
                with open(t_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if use_regex:
                    try:
                        new_content, n_subs = re.subn(find, replace, content, flags=re_flags)
                    except re.error as e:
                        logger.debug(f"Regex error in pattern: {e}")
                        overall_skipped += 1
                        break
                    if n_subs > 0:
                        with open(t_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        replacement_applied = True
                        modified_files.add(t_file)
                else:
                    if find in content:
                        new_content = content.replace(find, replace)
                        with open(t_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        replacement_applied = True
                        modified_files.add(t_file)

            if replacement_applied:
                overall_applied += 1
            else:
                logger.debug(f"Resource pattern not found anywhere: {find[:60]}...")
                overall_skipped += 1
                if not skip_on_fail:
                    raise ResourcePatchError(
                        f"Resource patch failed in {target_rel}: "
                        f"pattern not found: {find[:80]}"
                    )

        msg = f"{overall_applied} applied across {len(modified_files)} modified file(s) ({len(target_files)} scanned)"
        status = "applied" if overall_applied > 0 else "skipped"
        result = _make_result(patch_file_rel, status, msg)
        results.append(result)
        logger.patch_result(patch_file_rel, status, msg)

    return results


def _make_result(name: str, status: str, message: str = "") -> Dict[str, Any]:
    """Create a standardised patch result dict."""
    return {
        "name": name,
        "type": "resources",
        "status": status,
        "message": message,
    }
