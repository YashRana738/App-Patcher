#!/usr/bin/env python3
"""
APK Porter — Modular Android APK Patching Framework

A production-grade, config-driven APK patcher supporting:
  - Manifest patching (regex + exact string)
  - Resource patching (strings, colors, etc.)
  - Smali/DEX patching (find/replace in decompiled bytecode)
  - Class injection (copy new smali trees)
  - Automatic repacking and signing

Usage:
    python porter.py
    python porter.py --input path/to/app.apk
    python porter.py --input app.apk --dry-run
    python porter.py --input app.apk --verbose --keep-build
"""

import argparse
import os
import shutil
import sys
import time
from typing import Any, Dict, List

from bin.modules import logger
from bin.modules.exceptions import APKPorterError
from bin.modules.config_loader import (
    load_json,
    validate_tools,
    validate_patches_config,
    resolve_path,
)
from bin.modules.apktool_module import decode_apk
from bin.modules.manifest_module import apply_manifest_patches
from bin.modules.resource_module import apply_resource_patches
from bin.modules.smali_module import apply_smali_patches
from bin.modules.inject_module import inject_smali_trees
from bin.modules.build_module import build_apk
from bin.modules.signer_module import sign_apk
from bin.modules.apks_module import is_apks_file, convert_to_standalone_apk
from bin.modules.report import print_summary





# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="APK Porter — Modular APK Patching Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python porter.py\n"
            "  python porter.py --input myapp.apk\n"
            "  python porter.py --input mybundle.apks\n"
            "  python porter.py --input myapp.apk --dry-run\n"
            "  python porter.py --input myapp.apk --verbose --keep-build\n"
        ),
    )

    parser.add_argument(
        "--input", "-i",
        help="Input APK/APKS path (default: first .apk/.apks in workspace/input/)",
        default=None,
    )
    parser.add_argument(
        "--config", "-c",
        help="Patches config file (default: bin/patches/config/patches.json)",
        default="bin/patches/config/patches.json",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output APK/APKS path (default: workspace/output/...)",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and apply patches but don't repack/sign",
    )
    parser.add_argument(
        "--keep-build",
        action="store_true",
        help="Keep the decoded/build directory after completion",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "--no-sign",
        action="store_true",
        help="Skip APK signing step",
    )

    return parser.parse_args()


def find_input_apk(input_dir: str) -> str:
    """
    Find the first .apk, .apks, .xapk, .apkm, .apk+, or .zip file in the input directory.

    Raises:
        FileNotFoundError: If no APK/APKS found.
    """
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    for f in os.listdir(input_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in [".apk", ".apks", ".xapk", ".zip", ".apkm", ".apk+", ".apkp"]:
            return os.path.join(input_dir, f)

    raise FileNotFoundError(f"No .apk or .apks files found in: {input_dir}")




def main() -> int:
    """Main entry point. Returns 0 on success, 1 on error."""
    args = parse_args()
    start_time = time.time()

    # ── Load configs ──────────────────────────────────────────────────────
    try:
        tools_config = load_json(resolve_path("bin/patches/config/tools.json", PROJECT_ROOT))
        build_config = load_json(resolve_path("bin/patches/config/build.json", PROJECT_ROOT))
        patches_config = load_json(resolve_path(args.config, PROJECT_ROOT))
    except APKPorterError as e:
        print(f"[FATAL] {e}")
        return 1

    # ── Setup logging ─────────────────────────────────────────────────────
    log_level = "DEBUG" if args.verbose else build_config.get("log_level", "INFO")
    log_dir = resolve_path(build_config.get("log_dir", "logs"), PROJECT_ROOT)
    logger.setup_logging(log_dir=log_dir, log_level=log_level)

    logger.section("APK PORTER START")

    # ── Validate configs ──────────────────────────────────────────────────
    try:
        validate_tools(tools_config, PROJECT_ROOT)
        validate_patches_config(patches_config)
    except APKPorterError as e:
        logger.fatal(str(e))
        return 1

    # ── Resolve input APK/APKS ───────────────────────────────────────────
    if args.input:
        input_path = os.path.abspath(args.input)
    else:
        input_dir = resolve_path(
            build_config.get("input_dir", "workspace/input"), PROJECT_ROOT
        )
        try:
            input_path = find_input_apk(input_dir)
        except FileNotFoundError as e:
            logger.fatal(str(e))
            return 1

    if not os.path.isfile(input_path):
        logger.fatal(f"Input file not found: {input_path}")
        return 1

    input_name = os.path.basename(input_path)
    size_mb = os.path.getsize(input_path) / (1024 * 1024)
    logger.info(f"Input Package: {input_name} ({size_mb:.1f} MB)")

    is_apks = is_apks_file(input_path)
    extracted_apks_dir = resolve_path("workspace/extracted_apks", PROJECT_ROOT)

    if is_apks:
        logger.info("Detected APKS/XAPK/APKM/APK+ split bundle — converting to standalone APK first")
        standalone_input_apk = resolve_path("workspace/converted_standalone.apk", PROJECT_ROOT)
        convert_to_standalone_apk(input_path, extracted_apks_dir, standalone_input_apk, tools_config, PROJECT_ROOT)
        target_apk = standalone_input_apk

    else:
        target_apk = input_path


    # ── Resolve output path ───────────────────────────────────────────────
    if args.output:
        final_output_path = os.path.abspath(args.output)
        if not final_output_path.lower().endswith(".apk"):
            final_output_path = os.path.splitext(final_output_path)[0] + ".apk"
    else:
        output_dir = resolve_path(
            build_config.get("output_dir", "workspace/output"), PROJECT_ROOT
        )
        os.makedirs(output_dir, exist_ok=True)
        base_name, _ = os.path.splitext(input_name)
        final_output_path = os.path.join(output_dir, f"{base_name}_ported.apk")

    output_apk = final_output_path

    # ── Resolve workspace paths ───────────────────────────────────────────
    decode_dir = resolve_path(
        build_config.get("decode_dir", "workspace/decoded"), PROJECT_ROOT
    )

    # Extract skip_on_fail from options
    options = patches_config.get("options", {})
    skip_on_fail = options.get("skip_on_fail", True)

    # ── Track all patch results ───────────────────────────────────────────
    all_results: List[Dict[str, Any]] = []
    final_apk = ""

    try:
        # ── Step 1: Decode APK ────────────────────────────────────────────
        logger.section("DECODE APK")
        decode_apk(target_apk, decode_dir, tools_config, PROJECT_ROOT)

        # ── Step 2: Manifest Patches ──────────────────────────────────────
        logger.section("MANIFEST PATCHES")
        results = apply_manifest_patches(
            decode_dir, patches_config, PROJECT_ROOT, skip_on_fail
        )
        all_results.extend(results)

        # ── Step 3: Resource Patches ──────────────────────────────────────
        logger.section("RESOURCE PATCHES")
        results = apply_resource_patches(
            decode_dir, patches_config, PROJECT_ROOT, skip_on_fail
        )
        all_results.extend(results)

        # ── Step 4: Smali Patches ─────────────────────────────────────────
        logger.section("SMALI PATCHES")
        results = apply_smali_patches(
            decode_dir, patches_config, PROJECT_ROOT, skip_on_fail
        )
        all_results.extend(results)

        # ── Step 5: Class Injection ───────────────────────────────────────
        logger.section("CLASS INJECTION")
        results = inject_smali_trees(
            decode_dir, patches_config, PROJECT_ROOT, skip_on_fail
        )
        all_results.extend(results)

        # ── Step 6: Dry-run check ─────────────────────────────────────────
        if args.dry_run:
            logger.section("DRY RUN COMPLETE")
            logger.info("Patches validated — no APK was built or signed.")
            print_summary(all_results)

            # Clean up decoded dir
            if not args.keep_build:
                shutil.rmtree(decode_dir, ignore_errors=True)
                if is_apks:
                    shutil.rmtree(extracted_apks_dir, ignore_errors=True)

            return 0

        # ── Step 7: Build APK ─────────────────────────────────────────────
        logger.section("BUILD APK")
        use_aapt2 = build_config.get("use_aapt2", True)
        temp_built_apk = resolve_path("workspace/temp_built.apk", PROJECT_ROOT)
        build_apk(decode_dir, temp_built_apk, tools_config, PROJECT_ROOT, use_aapt2)

        if os.path.exists(output_apk):
            try:
                os.remove(output_apk)
            except OSError as e:
                logger.debug(f"Could not remove {output_apk}: {e}")

        shutil.move(temp_built_apk, output_apk)

        # ── Step 8: Sign APK ──────────────────────────────────────────────
        if not args.no_sign and build_config.get("sign", True):
            logger.section("SIGN APK")
            final_apk = sign_apk(output_apk, tools_config, PROJECT_ROOT)
        else:
            logger.info("Signing skipped (--no-sign or config)")
            final_apk = output_apk


    except APKPorterError as e:
        logger.fatal(str(e))
        print_summary(all_results)

        return 1

    except Exception as e:
        logger.fatal(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # ── Cleanup ───────────────────────────────────────────────────────
        keep = args.keep_build or build_config.get("keep_build", False)
        if not keep:
            if os.path.isdir(decode_dir):
                logger.debug("Cleaning up decoded directory...")
                shutil.rmtree(decode_dir, ignore_errors=True)
            if is_apks and os.path.isdir(extracted_apks_dir):
                logger.debug("Cleaning up extracted APKS directory...")
                shutil.rmtree(extracted_apks_dir, ignore_errors=True)

    # ── Report ────────────────────────────────────────────────────────────
    print_summary(all_results)

    # ── Done ──────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.section("BUILD COMPLETE")
    logger.success(f"Output: {final_apk}")
    logger.info(f"Elapsed: {elapsed:.1f} seconds")

    return 0


if __name__ == "__main__":
    sys.exit(main())

