"""
Class injection module.

Copies entire smali directory trees from patches/inject/
into the highest-numbered smali_classesN/ directory in the decoded APK.

This is used for injecting hidden API wrappers, utility classes, etc.
"""

import os
import shutil
from typing import Any, Dict, List

from bin.modules import logger
from bin.modules.exceptions import ClassInjectionError


def get_target_smali_dir(decoded_dir: str) -> str:
    """
    Find the primary smali directory in the decoded APK.

    Returns the path to inject classes into (e.g. smali/).
    If 'smali/' does not exist, fall back to the first available smali directory.
    """
    target = "smali"
    full_path = os.path.join(decoded_dir, target)
    if os.path.isdir(full_path):
        return full_path

    # Fallback if 'smali' directory itself is missing
    smali_dirs: List[str] = []
    for item in os.listdir(decoded_dir):
        fp = os.path.join(decoded_dir, item)
        if os.path.isdir(fp) and item.startswith("smali"):
            smali_dirs.append(item)

    if not smali_dirs:
        raise ClassInjectionError(
            f"No smali directories found in {decoded_dir}"
        )

    smali_dirs.sort()
    return os.path.join(decoded_dir, smali_dirs[0])


def copy_tree(src: str, dst: str) -> int:
    """
    Recursively copy a directory tree, preserving structure.

    Returns:
        The number of files copied.
    """
    count = 0

    if not os.path.isdir(src):
        raise ClassInjectionError(f"Source directory not found: {src}")

    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_root = os.path.join(dst, rel)
        os.makedirs(target_root, exist_ok=True)

        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(target_root, f)
            shutil.copy2(src_file, dst_file)
            count += 1
            logger.debug(f"  Injected: {os.path.relpath(dst_file, dst)}")

    return count


def inject_smali_trees(
    decoded_dir: str,
    config: Dict[str, Any],
    project_root: str,
    skip_on_fail: bool = True,
) -> List[Dict[str, Any]]:
    """
    Inject all configured smali class trees into the decoded APK.

    Args:
        decoded_dir:  Path to the decoded APK directory.
        config:       Patches config dict.
        project_root: Project root for resolving inject directory paths.
        skip_on_fail: If True, skip inject dirs that don't exist.

    Returns:
        A list of patch result dicts.
    """
    results: List[Dict[str, Any]] = []
    inject_dirs = config.get("inject_dirs", [])

    if not inject_dirs:
        logger.info("No class injection configured — skipping")
        return results

    # Find target smali directory
    try:
        target_smali = get_target_smali_dir(decoded_dir)
    except ClassInjectionError as e:
        logger.error(str(e))
        if not skip_on_fail:
            raise
        return results

    logger.info(f"Injection target: {os.path.basename(target_smali)}/")

    for inject_dir_rel in inject_dirs:
        inject_dir = os.path.normpath(
            os.path.join(project_root, inject_dir_rel)
        )

        if not os.path.isdir(inject_dir):
            result = _make_result(
                inject_dir_rel, "skipped", f"Directory not found: {inject_dir}"
            )
            results.append(result)
            logger.patch_result(inject_dir_rel, "skipped", "Directory not found")
            if not skip_on_fail:
                raise ClassInjectionError(f"Inject directory not found: {inject_dir}")
            continue

        try:
            file_count = copy_tree(inject_dir, target_smali)
            msg = f"Injected {file_count} file(s) into {os.path.basename(target_smali)}/"
            result = _make_result(inject_dir_rel, "applied", msg)
            results.append(result)
            logger.patch_result(inject_dir_rel, "applied", msg)

        except Exception as e:
            msg = f"Injection failed: {e}"
            result = _make_result(inject_dir_rel, "failed", msg)
            results.append(result)
            logger.patch_result(inject_dir_rel, "failed", msg)
            if not skip_on_fail:
                raise ClassInjectionError(msg)

    return results


def _make_result(name: str, status: str, message: str = "") -> Dict[str, Any]:
    """Create a standardised patch result dict."""
    return {
        "name": name,
        "type": "classes",
        "status": status,
        "message": message,
    }
