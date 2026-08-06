#!/usr/bin/env python3
"""
Patch Builder — Compiles human-readable patch folders into deployable JSON files.

Each patch lives in its own folder under patches/ and contains:
  meta.json   — required: defines name, type, output, description, etc.
  find.txt    — required for non-inject patches: text to search for
  replace.txt — required for non-inject patches: replacement text
  find_2.txt / replace_2.txt ... — optional: multiple find/replace pairs

Supported patch types (set in meta.json):
  "manifest"  — patches AndroidManifest.xml
  "resources" — patches resource XML files (res/)
  "smali"     — patches smali bytecode across DEX classes
  "inject"    — copies smali class trees into the decoded APK

Usage:
  python patch_builder.py                    # build all patches in patches/
  python patch_builder.py --folder <path>    # build a single patch folder
  python patch_builder.py --extract <file> --start <n> --end <n>  # extract lines into find.txt
"""

import argparse
import json
import os
import shutil
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PATCHES_DIR  = os.path.join(PROJECT_ROOT, "patches")
OUTPUT_BASE  = os.path.join(PROJECT_ROOT, "bin", "patches")
CONFIG_PATH  = os.path.join(OUTPUT_BASE, "config", "patches.json")

# Subdirectories of bin/patches/ that get wiped on each build
WIPE_DIRS = ["manifest", "resources", "smali", "inject"]

# Maps patch type → (config key, default output subdir)
PATCH_TYPE_MAP: Dict[str, Tuple[str, str]] = {
    "manifest":  ("manifest_patches", "manifest"),
    "resources": ("resource_patches", "resources"),
    "resource":  ("resource_patches", "resources"),   # alias
    "smali":     ("smali_patches",    "smali"),
}


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_text(path: str) -> str:
    """Read a UTF-8 text file, stripping trailing newlines."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().rstrip("\n")


def write_json(path: str, data: dict) -> None:
    """Write a dict to a JSON file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_json(path: str) -> Optional[dict]:
    """Load a JSON file. Returns None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def copy_tree_skip_meta(src: str, dst: str) -> None:
    """
    Recursively copy src into dst, skipping meta.json at the root level.
    Creates dst (and parents) if they don't exist.
    """
    os.makedirs(dst, exist_ok=True)
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        dest_dir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(dest_dir, exist_ok=True)
        for fname in files:
            if rel == "." and fname == "meta.json":
                continue
            shutil.copy2(os.path.join(root, fname), os.path.join(dest_dir, fname))


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def resolve_output_rel(raw: str, default_subdir: str, name: str) -> str:
    """
    Resolve the output path stored in meta.json to a canonical relative path
    under bin/patches/.

    If raw is empty, the default is bin/patches/<subdir>/<name>.json
    If raw starts with "patches/", it is remapped to "bin/patches/..."
    Otherwise it's used as-is.
    """
    if not raw:
        return f"bin/patches/{default_subdir}/{name}.json"
    rel = raw.replace("\\", "/").rstrip("/")
    if rel.startswith("patches/"):
        rel = "bin/" + rel
    return rel


def resolve_inject_output_rel(raw: str) -> str:
    """
    Resolve the inject output path in meta.json to a canonical relative path
    under bin/patches/inject/.

    All inject paths collapse into bin/patches/inject (single target directory).
    """
    if not raw:
        return "bin/patches/inject"
    rel = raw.replace("\\", "/").rstrip("/")
    if rel.startswith("patches/"):
        rel = "bin/" + rel
    return rel


# ---------------------------------------------------------------------------
# find/replace pair loader
# ---------------------------------------------------------------------------

def load_replacements(folder: str, folder_name: str) -> Optional[List[Dict[str, str]]]:
    """
    Scan the patch folder for find*.txt / replace*.txt file pairs.

    Returns a list of {"find": ..., "replace": ...} dicts, or None on error.
    Requires at least one pair; every find file must have a matching replace file.
    """
    all_files = os.listdir(folder)
    find_files = sorted(f for f in all_files if f.startswith("find") and f.endswith(".txt"))

    if not find_files:
        print(f"  [SKIP] {folder_name}/ — no find.txt / find*.txt files found")
        return None

    replacements: List[Dict[str, str]] = []
    missing: List[str] = []

    for find_file in find_files:
        suffix = find_file[len("find"):]          # e.g. ".txt" or "_2.txt"
        replace_file = "replace" + suffix

        find_path    = os.path.join(folder, find_file)
        replace_path = os.path.join(folder, replace_file)

        if not os.path.isfile(replace_path):
            missing.append(replace_file)
            continue

        replacements.append({
            "find":    read_text(find_path),
            "replace": read_text(replace_path),
        })

    if missing:
        print(f"  [ERROR] {folder_name}/ — missing replace file(s): {', '.join(missing)}")
        return None

    return replacements


# ---------------------------------------------------------------------------
# Per-type patch data builders
# ---------------------------------------------------------------------------

def build_manifest_patch(meta: dict, replacements: List[dict], name: str, desc: str) -> dict:
    data: dict = {"name": name, "description": desc}

    if len(replacements) == 1:
        data["find"]    = replacements[0]["find"]
        data["replace"] = replacements[0]["replace"]
    else:
        data["replacements"] = replacements

    if meta.get("regex"):
        data["regex"] = True
        data["flags"] = meta.get("flags", "MULTILINE|DOTALL")

    return data


def build_resource_patch(meta: dict, replacements: List[dict], name: str, desc: str) -> dict:
    data = {
        "name":         name,
        "description":  desc,
        "target":       meta.get("target", "res/values/strings.xml"),
        "replacements": replacements,
    }
    if meta.get("regex"):
        data["regex"] = True
        data["flags"] = meta.get("flags", "MULTILINE")
    return data


def build_smali_patch(meta: dict, replacements: List[dict], name: str, desc: str) -> dict:
    data = {
        "name":         name,
        "description":  desc,
        "target":       meta.get("target", ""),   # empty = all smali files
        "replacements": replacements,
    }
    if meta.get("regex"):
        data["regex"] = True
        data["flags"] = meta.get("flags", "MULTILINE")
    return data


# ---------------------------------------------------------------------------
# Main patch builder
# ---------------------------------------------------------------------------

def build_patch_from_folder(folder: str) -> Optional[Dict[str, Any]]:
    """
    Process a single patch source folder.

    Returns a result dict:
        {
            "name":        <str>,
            "patch_type":  <"manifest"|"resources"|"smali"|"classes">,
            "output_rel":  <relative path from project root>,
            "output_path": <absolute path>,
            "patch_data":  <dict to write as JSON, empty for inject>,
        }
    Or None if the folder should be skipped / failed.
    """
    folder_name = os.path.basename(os.path.normpath(folder))
    meta_path   = os.path.join(folder, "meta.json")

    # ── Load meta.json ────────────────────────────────────────────────────
    if not os.path.isfile(meta_path):
        # Fallback: nameless inject folder
        if folder_name.lower().startswith("[inject]"):
            return _build_inject_result(folder, folder_name, "bin/patches/inject")
        print(f"  [SKIP] {folder_name}/ — missing meta.json")
        return None

    meta = read_json(meta_path)
    if meta is None:
        print(f"  [ERROR] {folder_name}/meta.json — invalid JSON")
        return None

    name       = meta.get("name", folder_name)
    desc       = meta.get("description", "")
    patch_type = meta.get("type", "manifest").lower()
    output_raw = meta.get("output", "")

    # ── Inject / class-copy patches ───────────────────────────────────────
    if patch_type in ("inject", "classes"):
        output_rel = resolve_inject_output_rel(output_raw)
        return _build_inject_result(folder, folder_name, output_rel, name=name)

    # ── Standard find/replace patches ────────────────────────────────────
    type_info = PATCH_TYPE_MAP.get(patch_type)
    if type_info is None:
        print(f"  [ERROR] {folder_name}/meta.json — unknown type: '{patch_type}'")
        return None

    config_key, default_subdir = type_info

    replacements = load_replacements(folder, folder_name)
    if replacements is None:
        return None

    # Build patch data dict according to type
    if patch_type == "manifest":
        patch_data = build_manifest_patch(meta, replacements, name, desc)
    elif patch_type in ("resources", "resource"):
        patch_data = build_resource_patch(meta, replacements, name, desc)
    else:  # smali
        patch_data = build_smali_patch(meta, replacements, name, desc)

    # Normalise the config key (resource → resources)
    normalised_type = "resources" if patch_type == "resource" else patch_type

    output_rel  = resolve_output_rel(output_raw, default_subdir, name)
    output_path = os.path.join(PROJECT_ROOT, output_rel)

    return {
        "name":        name,
        "patch_type":  normalised_type,
        "output_rel":  output_rel,
        "output_path": output_path,
        "patch_data":  patch_data,
    }


def _build_inject_result(
    folder: str,
    folder_name: str,
    output_rel: str,
    name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Copy a smali class tree into the resolved output directory."""
    output_path = os.path.normpath(os.path.join(PROJECT_ROOT, output_rel))
    try:
        copy_tree_skip_meta(folder, output_path)
    except Exception as exc:
        print(f"  [ERROR] {folder_name}/ — failed to copy class tree: {exc}")
        return None

    return {
        "name":        name or folder_name,
        "patch_type":  "classes",
        "output_rel":  output_rel,
        "output_path": output_path,
        "patch_data":  {},
    }


# ---------------------------------------------------------------------------
# Config updater
# ---------------------------------------------------------------------------

def update_patches_config(built_patches: List[Dict[str, Any]]) -> None:
    """
    Regenerate bin/patches/config/patches.json from the freshly built patches.

    Preserves existing user options and any inject_dirs that don't point into
    the auto-generated bin/patches/inject tree.
    """
    existing = read_json(CONFIG_PATH) or {}

    # Keep any user-managed inject dirs that weren't generated by this builder
    def is_generated_inject(d: str) -> bool:
        lo = d.lower().replace("\\", "/").rstrip("/")
        return lo in ("bin/patches/inject", "patches/inject") or \
               lo.startswith("bin/patches/inject/") or \
               lo.startswith("patches/inject/")

    preserved_inject_dirs = [
        d for d in existing.get("inject_dirs", [])
        if not is_generated_inject(d)
    ]

    new_config: Dict[str, Any] = {
        "manifest_patches": [],
        "resource_patches": [],
        "smali_patches":    [],
        "inject_dirs":      preserved_inject_dirs,
        "options":          existing.get("options", {
            "skip_on_fail": True,
            "strict_mode":  False,
            "log_level":    "INFO",
        }),
    }

    type_to_key = {
        "manifest":  "manifest_patches",
        "resources": "resource_patches",
        "smali":     "smali_patches",
    }

    for patch in built_patches:
        rel = patch["output_rel"].replace("\\", "/")
        if patch["patch_type"] == "classes":
            if rel not in new_config["inject_dirs"]:
                new_config["inject_dirs"].append(rel)
        else:
            key = type_to_key.get(patch["patch_type"])
            if key:
                new_config[key].append(rel)

    write_json(CONFIG_PATH, new_config)

    print(f"  [OK] Updated bin/patches/config/patches.json")
    for key in ("manifest_patches", "resource_patches", "smali_patches"):
        count = len(new_config[key])
        if count:
            print(f"       {key}: {count} patch(es)")
    inject_count = len(new_config["inject_dirs"])
    if inject_count:
        print(f"       inject_dirs: {inject_count} director{'y' if inject_count == 1 else 'ies'}")


# ---------------------------------------------------------------------------
# Build all
# ---------------------------------------------------------------------------

def build_all() -> None:
    """Discover and build every patch folder under patches/."""
    if not os.path.isdir(PATCHES_DIR):
        print(f"  [ERROR] patches/ directory not found: {PATCHES_DIR}")
        print(f"  Create patch folders in patches/<patch_name>/")
        sys.exit(1)

    # Collect subdirectories, ignoring legacy 'src'
    folders = sorted(
        os.path.join(PATCHES_DIR, d)
        for d in os.listdir(PATCHES_DIR)
        if os.path.isdir(os.path.join(PATCHES_DIR, d)) and d.lower() != "src"
    )

    if not folders:
        print(f"  [INFO] No patch folders found in patches/")
        print(f"  Create a folder with find.txt + replace.txt + meta.json")
        return

    print(f"\n{'=' * 60}")
    print(f"  PATCH BUILDER")
    print(f"  Source: patches/ ({len(folders)} patch folder(s))")
    print(f"{'=' * 60}\n")

    # Wipe generated output dirs before rebuilding
    for subdir in WIPE_DIRS:
        path = os.path.join(OUTPUT_BASE, subdir)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except Exception as exc:
                print(f"  [WARN] Could not wipe {path}: {exc}")

    built:   int = 0
    skipped: int = 0
    failed:  int = 0
    built_patches: List[Dict[str, Any]] = []

    for folder in folders:
        folder_name = os.path.basename(folder)
        result = build_patch_from_folder(folder)

        if result is None:
            skipped += 1
            continue

        try:
            if result["patch_type"] != "classes":
                write_json(result["output_path"], result["patch_data"])
            rel = os.path.relpath(result["output_path"], PROJECT_ROOT)
            print(f"  [OK] {folder_name}/ → {rel}")
            built += 1
            built_patches.append(result)
        except Exception as exc:
            print(f"  [ERROR] {folder_name}/ — could not write output: {exc}")
            failed += 1

    if built_patches:
        print()
        update_patches_config(built_patches)

    print(f"\n{'-' * 60}")
    print(f"  Built: {built}  |  Skipped: {skipped}  |  Failed: {failed}")
    print(f"{'-' * 60}\n")


# ---------------------------------------------------------------------------
# Extract helper
# ---------------------------------------------------------------------------

def extract_block(file_path: str, start: int, end: int, output: str = "find.txt") -> None:
    """Extract a range of lines from a file and save them to output."""
    if not os.path.isfile(file_path):
        print(f"  [ERROR] File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total = len(lines)
    if not (1 <= start <= end <= total):
        print(f"  [ERROR] Invalid range {start}-{end} (file has {total} lines)")
        sys.exit(1)

    block = "".join(lines[start - 1 : end])
    with open(output, "w", encoding="utf-8") as f:
        f.write(block)

    preview_lines = block.split("\n")
    print(f"\n  [OK] Extracted lines {start}-{end} → {output}")
    print(f"\n  Preview ({end - start + 1} lines):")
    for i, line in enumerate(preview_lines[:20], start=start):
        print(f"    {i:4d} | {line}")
    remaining = (end - start + 1) - 20
    if remaining > 0:
        print(f"    ... ({remaining} more lines)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch Builder — compile patches/ into bin/patches/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Default (no args): build ALL patches from patches/

            Patch folder structure:
              patches/<patch_name>/
              ├── meta.json      (required)
              ├── find.txt       (required for non-inject patches)
              └── replace.txt    (required for non-inject patches)

            meta.json keys:
              name        — patch identifier (used as output filename)
              description — human-readable description
              type        — "manifest" | "resources" | "smali" | "inject"
              output      — optional override for output path (relative to patches/)
              target      — file/dir to target (resources/smali patches)
              regex       — true/false (manifest patches only)
              flags       — regex flags, default: "MULTILINE|DOTALL"
        """),
    )
    parser.add_argument("--folder",  "-f", help="Build a single patch folder")
    parser.add_argument("--extract", "-e", help="Extract lines from a file into find.txt")
    parser.add_argument("--start",   "-s", type=int, help="Start line for --extract (1-indexed)")
    parser.add_argument("--end",           type=int, help="End line for --extract (1-indexed)")
    parser.add_argument("--output",  "-o", help="Output file for --extract (default: find.txt)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.extract:
        if not args.start or not args.end:
            print("  [ERROR] --extract requires --start and --end")
            sys.exit(1)
        extract_block(args.extract, args.start, args.end, output=args.output or "find.txt")

    elif args.folder:
        folder = os.path.abspath(args.folder)
        result = build_patch_from_folder(folder)
        if result is None:
            sys.exit(1)
        if result["patch_type"] != "classes":
            write_json(result["output_path"], result["patch_data"])
        print(f"  [OK] {result['name']} → {result['output_path']}")

    else:
        build_all()


if __name__ == "__main__":
    main()
