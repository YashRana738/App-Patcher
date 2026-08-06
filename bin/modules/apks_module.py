"""
APKS module — handles extraction, base APK resolution, and bundle-to-standalone conversion
using REAndroid/APKEditor library or internal fallbacks.
"""

import os
import re
import shutil
import zipfile
from typing import Dict, List, Optional

from bin.modules import logger
from bin.modules.config_loader import resolve_tool_path
from bin.modules.exceptions import APKPorterError
from bin.modules.shell import run_command


class APKSError(APKPorterError):
    """Raised when APKS extraction, resolution, or repackaging fails."""
    pass


def is_apks_file(file_path: str) -> bool:
    """Check if the given file path is an APKS/XAPK/APKM/APK+ bundle."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [".apks", ".xapk", ".zip", ".apkm", ".apk+", ".apkp"]


def extract_apks(apks_path: str, extract_dir: str) -> str:
    """
    Extract an APKS/XAPK zip package into extract_dir.

    Args:
        apks_path:   Path to the input .apks / .xapk archive.
        extract_dir: Directory where contents will be extracted.

    Returns:
        Absolute path to extract_dir.
    """
    if not os.path.isfile(apks_path):
        raise APKSError(f"APKS file not found: {apks_path}")

    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
    os.makedirs(extract_dir, exist_ok=True)

    logger.info(f"Extracting APKS bundle: {os.path.basename(apks_path)}")
    try:
        with zipfile.ZipFile(apks_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except Exception as e:
        raise APKSError(f"Failed to extract APKS bundle: {e}")

    logger.success(f"Extracted APKS to: {extract_dir}")
    return extract_dir


def find_base_apk(extract_dir: str) -> str:
    """
    Find the primary base APK inside an extracted APKS directory.

    Order of search:
      1. base.apk
      2. standalone.apk
      3. Any single .apk if only one exists in root or subdirectories.

    Raises:
        APKSError: If no suitable base APK is found.
    """
    if not os.path.isdir(extract_dir):
        raise APKSError(f"Extracted APKS directory not found: {extract_dir}")

    apk_files: List[str] = []
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.lower().endswith(".apk"):
                apk_files.append(os.path.join(root, f))

    if not apk_files:
        raise APKSError(f"No .apk files found inside extracted bundle: {extract_dir}")

    # 1. Look for base.apk
    for apk in apk_files:
        if os.path.basename(apk).lower() == "base.apk":
            return apk

    # 2. Look for standalone.apk
    for apk in apk_files:
        if os.path.basename(apk).lower() == "standalone.apk":
            return apk

    # 3. Default to first .apk found
    logger.warn(f"Could not explicitly identify base.apk; using: {os.path.basename(apk_files[0])}")
    return apk_files[0]


def _get_max_dex_index(namelist: List[str]) -> int:
    """Find the highest DEX index present in zip file namelist (e.g. classes3.dex -> 3)."""
    max_idx = 1
    for name in namelist:
        if name == "classes.dex":
            max_idx = max(max_idx, 1)
        else:
            m = re.match(r"^classes(\d+)\.dex$", name)
            if m:
                max_idx = max(max_idx, int(m.group(1)))
    return max_idx


def merge_all_split_apks(extract_dir: str, target_apk_path: str) -> None:
    """
    Comprehensively merge ALL split APKs (native libraries lib/, assets/, DEX bytecode files,
    and root resource entries) into the primary target APK to create a 100% complete standalone APK.
    """
    apk_files = []
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.lower().endswith(".apk"):
                full_path = os.path.join(root, f)
                if os.path.abspath(full_path) != os.path.abspath(target_apk_path):
                    apk_files.append(full_path)

    if not apk_files:
        return

    logger.info(f"Merging content from {len(apk_files)} split APKs into standalone APK...")
    
    with zipfile.ZipFile(target_apk_path, 'r') as target_zip:
        target_namelist = target_zip.namelist()
        existing_entries = set(target_namelist)
        next_dex_idx = _get_max_dex_index(target_namelist) + 1

    merged_count = 0
    merged_dex_count = 0

    with zipfile.ZipFile(target_apk_path, 'a', compression=zipfile.ZIP_DEFLATED) as target_zip:
        for split_apk in apk_files:
            logger.debug(f"Processing split APK: {os.path.basename(split_apk)}")
            with zipfile.ZipFile(split_apk, 'r') as split_zip:
                for member in split_zip.infolist():
                    fname = member.filename

                    # Skip directories, manifest, signature files, and resources.arsc
                    if fname.endswith("/") or fname == "AndroidManifest.xml" or fname == "resources.arsc":
                        continue
                    if fname.startswith("META-INF/") and (fname.endswith(".SF") or fname.endswith(".RSA") or fname.endswith(".MF")):
                        continue

                    # 1. Merge DEX files from feature splits under next available classesN.dex name
                    if fname.startswith("classes") and fname.endswith(".dex"):
                        new_dex_name = f"classes{next_dex_idx}.dex" if next_dex_idx > 1 else "classes.dex"
                        next_dex_idx += 1
                        data = split_zip.read(fname)
                        target_zip.writestr(new_dex_name, data)
                        existing_entries.add(new_dex_name)
                        merged_dex_count += 1
                        logger.debug(f"  Merged DEX: {fname} -> {new_dex_name}")
                        continue

                    # 2. Merge lib/, assets/, kotlin/, META-INF/services/ and root resources
                    if fname not in existing_entries:
                        data = split_zip.read(fname)
                        target_zip.writestr(member, data)
                        existing_entries.add(fname)
                        merged_count += 1
                        logger.debug(f"  Merged entry: {fname}")

    logger.success(f"Merged {merged_count} file(s) and {merged_dex_count} DEX bytecode file(s) from split APKs into standalone APK")


def merge_bundle_with_apkeditor(
    apks_path: str,
    output_apk_path: str,
    tools: Dict[str, str],
    project_root: str,
) -> bool:
    """
    Merge an APKS/APKM/XAPK/APK+ split bundle into a standalone APK using APKEditor.jar library.
    """
    apkeditor_rel = tools.get("apkeditor", "bin/tools/APKEditor.jar")
    apkeditor_path = resolve_tool_path("apkeditor", apkeditor_rel, project_root)
    java = resolve_tool_path("java", tools.get("java", "java"), project_root)

    if not os.path.isfile(apkeditor_path):
        logger.warn(f"APKEditor.jar not found at {apkeditor_path} — falling back to internal merger")
        return False

    out_dir = os.path.dirname(output_apk_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    logger.info(f"Merging split bundle via APKEditor library: {os.path.basename(apks_path)}")
    cmd = [
        java,
        "-jar",
        apkeditor_path,
        "m",
        "-i", apks_path,
        "-o", output_apk_path,
        "-f"
    ]

    try:
        run_command(cmd, description="APKEditor merge")
        if os.path.isfile(output_apk_path) and os.path.getsize(output_apk_path) > 0:
            size_mb = os.path.getsize(output_apk_path) / (1024 * 1024)
            logger.success(f"APKEditor merged bundle successfully: {output_apk_path} ({size_mb:.1f} MB)")
            return True
    except Exception as e:
        logger.warn(f"APKEditor merge failed ({e}) — falling back to internal merger")

    return False


def convert_to_standalone_apk(
    apks_path: str,
    extract_dir: str,
    output_apk_path: str,
    tools: Optional[Dict[str, str]] = None,
    project_root: Optional[str] = None,
) -> str:
    """
    Extract an APKS/XAPK/APKM/APK+ bundle and convert it into a single standalone .apk file,
    merging native libraries (lib/ ABIs), DEX files, and assets from all split APKs.
    Uses APKEditor.jar library for industry-standard resource remapping and ABI/DEX merging.

    Args:
        apks_path:        Path to the input APKS/APKM archive.
        extract_dir:      Directory to extract temporary bundle contents.
        output_apk_path:  Target path for the converted standalone .apk file.
        tools:            Tool paths dict from tools.json.
        project_root:     Absolute path to the project root.

    Returns:
        Absolute path to output_apk_path.
    """
    logger.section("CONVERT BUNDLE TO STANDALONE APK")

    if tools and project_root:
        if merge_bundle_with_apkeditor(apks_path, output_apk_path, tools, project_root):
            return output_apk_path

    # Fallback if tools not provided or APKEditor failed
    extract_apks(apks_path, extract_dir)
    base_apk = find_base_apk(extract_dir)

    out_dir = os.path.dirname(output_apk_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if os.path.exists(output_apk_path):
        try:
            os.remove(output_apk_path)
        except OSError:
            pass

    shutil.copy2(base_apk, output_apk_path)
    merge_all_split_apks(extract_dir, output_apk_path)
    logger.success(f"Converted bundle to complete standalone APK: {output_apk_path}")
    return output_apk_path
