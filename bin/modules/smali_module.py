"""
Smali patcher module.

Applies find/replace patches to decompiled .smali files inside the decoded APK.
Searches across all smali directories (smali/, smali_classes2/, smali_classes3/, etc.)

Each patch file is a JSON object with:
    "target":       Filename of the .smali file (e.g. "SomeClass.smali")
    "replacements": List of {"find": "...", "replace": "..."} objects.
"""

import os
import json
import re
from typing import Any, Dict, List, Optional

from bin.modules import logger
from bin.modules.exceptions import SmaliPatchError


def find_smali_targets(decoded_dir: str, target_name: str) -> List[str]:
    """
    Find all matching .smali files across all smali* directories.
    If target_name is a specific file path (e.g. 'com/example/ClassName.smali'),
    it returns all exact matches.
    If target_name is a directory (e.g. 'com/example/' or 'com/example'),
    it returns all .smali files within that directory across all smali folders.
    If target_name is just a filename (e.g. 'ClassName.smali'),
    it returns all files with that name.
    """
    targets = []
    # Normalise separators
    target_name = target_name.strip().replace("\\", "/")
    
    if target_name in ("", ".", "smali"):
        for root, dirs, files in os.walk(decoded_dir):
            rel = os.path.relpath(root, decoded_dir).replace("\\", "/")
            top_dir = rel.split("/")[0] if rel != "." else ""
            if top_dir.startswith("smali"):
                for f in files:
                    if f.endswith(".smali"):
                        targets.append(os.path.join(root, f))
        return targets

    is_path = "/" in target_name

    for root, dirs, files in os.walk(decoded_dir):
        rel = os.path.relpath(root, decoded_dir).replace("\\", "/")
        top_dir = rel.split("/")[0] if rel != "." else ""

        if top_dir and not top_dir.startswith("smali"):
            continue

        if not is_path:
            # Just matching filename
            if target_name in files:
                targets.append(os.path.join(root, target_name))
        else:
            # Matching a path or directory
            # rel looks like 'smali/com/example'
            # we want to strip the 'smali' prefix to get 'com/example'
            if "/" in rel:
                _, rel_no_smali = rel.split("/", 1)
            else:
                rel_no_smali = ""

            # Check if this directory exactly matches or starts with the target path
            # (meaning it's the target directory or a subdirectory)
            if rel_no_smali == target_name or rel_no_smali.startswith(target_name + "/"):
                for f in files:
                    if f.endswith(".smali"):
                        targets.append(os.path.join(root, f))
            # Or if target_name is a specific file, check if we are in its directory
            else:
                target_dir, target_file = os.path.split(target_name)
                if rel_no_smali == target_dir and target_file in files:
                    targets.append(os.path.join(root, target_file))

    return targets


def apply_smali_patches(
    decoded_dir: str,
    config: Dict[str, Any],
    project_root: str,
    skip_on_fail: bool = True,
) -> List[Dict[str, Any]]:
    """
    Apply all smali patches defined in config.

    Args:
        decoded_dir:  Path to the decoded APK directory.
        config:       Patches config dict.
        project_root: Project root for resolving patch file paths.
        skip_on_fail: If True, skip patches that fail.

    Returns:
        A list of patch result dicts.
    """
    results: List[Dict[str, Any]] = []
    patch_files = config.get("smali_patches", [])

    if not patch_files:
        logger.info("No smali patches configured — skipping")
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
                raise SmaliPatchError(f"Patch file not found: {patch_file}")
            continue

        try:
            with open(patch_file, "r", encoding="utf-8") as pf:
                patch = json.load(pf)
        except json.JSONDecodeError as e:
            result = _make_result(patch_file_rel, "failed", f"Invalid JSON: {e}")
            results.append(result)
            logger.patch_result(patch_file_rel, "failed", f"Invalid JSON: {e}")
            if not skip_on_fail:
                raise SmaliPatchError(f"Invalid JSON in {patch_file}: {e}")
            continue

        # Find target smali file (empty target = all smali files)
        target_name = patch.get("target", "")

        target_files = find_smali_targets(decoded_dir, target_name)

        if not target_files:
            msg = f"Smali targets not found: {target_name}"
            result = _make_result(patch_file_rel, "skipped", msg)
            results.append(result)
            logger.patch_result(patch_file_rel, "skipped", msg)
            if not skip_on_fail:
                raise SmaliPatchError(msg)
            continue

        logger.debug(f"Found {len(target_files)} smali target(s) for {target_name}")

        # Regex mode can be set at patch level or per-entry level
        patch_regex = patch.get("regex", False)
        patch_flags_str = patch.get("flags", "MULTILINE")

        replacements = patch.get("replacements", [])
        overall_applied = 0
        overall_skipped = 0
        modified_files = set()

        for entry in replacements:
            find    = entry.get("find", "")
            replace = entry.get("replace", "")
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
                logger.debug(f"Smali pattern not found anywhere: {find[:60]}...")
                overall_skipped += 1
                if not skip_on_fail:
                    raise SmaliPatchError(
                        f"Smali patch failed in {target_name}: "
                        f"pattern not found:\n{find[:120]}"
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
        "type": "smali",
        "status": status,
        "message": message,
    }
