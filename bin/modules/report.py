"""
Report generator for APK Porter.

Generates a JSON report summarising all patch results,
and optionally prints a human-readable summary to the console.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from bin.modules import logger


def generate_report(
    input_apk: str,
    output_apk: str,
    config_file: str,
    patch_results: List[Dict[str, Any]],
    report_dir: str,
) -> str:
    """
    Generate a JSON report of the patching session.

    Args:
        input_apk:     Path to the original input APK.
        output_apk:    Path to the final signed APK (or empty if failed).
        config_file:   Path to the patches config used.
        patch_results: List of all patch result dicts.
        report_dir:    Directory to save the report file.

    Returns:
        The path to the generated report file.
    """
    os.makedirs(report_dir, exist_ok=True)

    # Tally stats
    applied = sum(1 for r in patch_results if r.get("status") == "applied")
    skipped = sum(1 for r in patch_results if r.get("status") == "skipped")
    failed = sum(1 for r in patch_results if r.get("status") == "failed")
    total = len(patch_results)

    report = {
        "timestamp": datetime.now().isoformat(),
        "input_apk": os.path.basename(input_apk),
        "output_apk": os.path.basename(output_apk) if output_apk else "N/A",
        "config_file": config_file,
        "total_patches": total,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "patches": patch_results,
        "summary": (
            f"Successfully applied {applied} of {total} patches. "
            f"{skipped} skipped, {failed} failed."
        ),
    }

    # Write report
    report_filename = f"patch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = os.path.join(report_dir, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"Report saved: {report_path}")
    return report_path


def print_summary(patch_results: List[Dict[str, Any]]) -> None:
    """Print a human-readable summary table to the console."""
    applied = sum(1 for r in patch_results if r.get("status") == "applied")
    skipped = sum(1 for r in patch_results if r.get("status") == "skipped")
    failed = sum(1 for r in patch_results if r.get("status") == "failed")
    total = len(patch_results)

    logger.section("PATCH SUMMARY")
    logger.info(f"  Total patches : {total}")
    logger.success(f"  Applied       : {applied}")

    if skipped > 0:
        logger.warn(f"  Skipped       : {skipped}")
    else:
        logger.info(f"  Skipped       : {skipped}")

    if failed > 0:
        logger.error(f"  Failed        : {failed}")
    else:
        logger.info(f"  Failed        : {failed}")

    print()  # blank line after summary
