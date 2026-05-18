# Patch Building Guide

This document outlines the conventions and procedures for creating, configuring, and compiling patches within the App-Patcher framework.

## 1. Patch Builder Architecture

The `patch_builder.py` script compiles human-readable patch directories (located in `patches/`) into optimized JSON definitions (stored in `bin/patches/`). 

During compilation, the builder:
1. Parses the `meta.json` file in each patch directory to determine the patch type, target, and output path.
2. Identifies and pairs corresponding search and replacement text files.
3. Updates the global orchestration index (`bin/patches/config/patches.json`) to register the compiled patches for execution.

## 2. Patch Directory Structure

A standard patch requires a dedicated directory under `patches/` (e.g., `patches/[Smali] Example_Patch/`). The directory must contain a `meta.json` configuration file alongside the necessary text replacement files.

### Configuration Specification (`meta.json`)

```json
{
  "name": "Example_Patch",
  "description": "Brief description of the patch behavior.",
  "type": "smali",
  "target": "Lcom/example/app/TargetClass.smali",
  "output": "patches/smali/Example_Patch.json",
  "regex": true,
  "flags": "MULTILINE|DOTALL"
}
```

* **`name`** (String): A unique identifier for the patch.
* **`description`** (String): Summary of the patch operations.
* **`type`** (String): The target subsystem. Valid values are `"manifest"`, `"resources"`, `"smali"`, or `"inject"`.
* **`target`** (String): The file or path to modify.
  * `"manifest"`: Defaults to `AndroidManifest.xml` if unspecified.
  * `"resources"`: The path to the resource XML (e.g., `res/values/strings.xml`). Set to `"res/"` to target all resource files.
  * `"smali"`: The path to the class file (e.g., `Lcom/example/Target.smali`). Leave empty (`""`) to apply the patch globally across all smali files.
* **`output`** (String): The relative output path for the compiled JSON. Paths starting with `"patches/"` are automatically mapped to `"bin/patches/"`.
* **`regex`** (Boolean): Set to `true` to enable regular expression processing.
* **`flags`** (String): Pipe-separated Python regex flags (e.g., `MULTILINE`, `DOTALL`). Defaults to `MULTILINE`.

## 3. File Resolution Rules

The builder resolves search and replacement blocks based on filename conventions:

* **Single Replacement**: Use `find.txt` and `replace.txt`.
* **Sequential Replacements**: For multiple distinct operations in a single patch, use numeric suffixes (e.g., `find.txt` / `replace.txt`, `find_2.txt` / `replace_2.txt`).
* **Named Replacements**: For logically grouped operations, use descriptive suffixes (e.g., `find_feature.txt` / `replace_feature.txt`).

## 4. Regular Expression Engine

When `"regex": true` is specified, modifications are processed using Python's `re.subn` module.

### Capture Groups
Standard regex capture groups `()` can be referenced in the replacement text using back-references (`\1`, `\2`, etc.). The `MULTILINE` flag is enabled by default, causing `^` and `$` to match line boundaries. Use `DOTALL` if `.` should match newline characters.

## 5. Examples

The following examples demonstrate the directory layout and file contents for various patch types.

### Example 1: Smali Patch with Regex

Dynamically match register variables and inject instructions.

**Directory:** `patches/[Smali] Force_State/`

**`meta.json`**:
```json
{
  "name": "Force_State",
  "description": "Injects state override and sets predefined flags.",
  "type": "smali",
  "target": "",
  "regex": true,
  "flags": "MULTILINE",
  "output": "patches/smali/Force_State.json"
}
```

**`find_state.txt`**:
```regex
([ \t]*)(iput-boolean (\w+), (\w+), (L[^;]+;)->isTargetDevice:Z)
```

**`replace_state.txt`**:
```text
\1const/4 \3, 0x1
\1\2
\1iput-boolean \3, \4, \5->isPreInstalled:Z
```
*Note: `\1` captures indentation, `\2` captures the original instruction, `\3` and `\4` capture registers, and `\5` captures the class descriptor.*

### Example 2: Smali Patch (Conditional Bypass)

Remove a conditional branch prior to a specific object reference.

**Directory:** `patches/[Smali] Bypass_Check/`

**`meta.json`**:
```json
{
  "name": "Bypass_Check",
  "description": "Removes conditional branching before media evaluation.",
  "type": "smali",
  "target": "",
  "regex": true,
  "flags": "MULTILINE",
  "output": "patches/smali/Bypass_Check.json"
}
```

**`find.txt`**:
```regex
([ \t]*)if-ne\s+\w+,\s+\w+,\s+:\w+\r?\n[ \t]*\r?\n([ \t]*sget-object\s+\w+,\s+L[^;]+;->PROP_TARGET_EVAL:L[^;]+;)
```

**`replace.txt`**:
```text
\2
```

### Example 3: Resource XML Patch

Modify string definitions across resource dictionaries.

**Directory:** `patches/[Res] Rename_Application/`

**`meta.json`**:
```json
{
  "name": "Rename_Application",
  "description": "Updates the primary application display name.",
  "type": "resources",
  "target": "res/",
  "output": "patches/resources/Rename_Application.json"
}
```

**`find.txt`**:
```xml
<string name="app_name">OriginalName</string>
```

**`replace.txt`**:
```xml
<string name="app_name">NewName</string>
```

### Example 4: Manifest Patch

Inject custom attributes into the AndroidManifest.

**Directory:** `patches/[Manifest] Update_Proxy/`

**`meta.json`**:
```json
{
  "name": "Update_Proxy",
  "description": "Configures a custom application class in the manifest.",
  "type": "manifest",
  "target": "AndroidManifest.xml",
  "regex": true,
  "flags": "MULTILINE",
  "output": "patches/manifest/Update_Proxy.json"
}
```

**`find.txt`**:
```regex
<application([^>]*)android:name="([^"]*)"
```

**`replace.txt`**:
```text
<application\1android:name="com.custom.proxy.ProxyApplication"
```

### Example 5: Class Injection

Inject custom Smali directories directly into the decompiled APK. The injection module prioritizes the `smali/` primary DEX directory to ensure base class availability.

**Directory:** `patches/[Inject] Base_Dependency/`

**Layout:**
```text
patches/[Inject] Base_Dependency/
├── meta.json
└── smali/
    └── com/
        └── custom/
            └── proxy/
                └── ProxyApplication.smali
```

**`meta.json`**:
```json
{
  "name": "Base_Dependency",
  "description": "Injects the ProxyApplication class tree.",
  "type": "inject",
  "target": "/",
  "output": "patches/Inject/Base_Dependency/"
}
```

## 6. Application Signing and Keystores

The framework handles APK signing via the `signer_module.py`, supporting custom developer keys located in `workspace/keys/`.

### Supported Keystore Formats
1. **Standalone PKCS12 (`.p12`)**: If a valid `.p12` file exists in the directory, it is used immediately.
2. **Raw Keys (`.pk8` and `.pem`)**: If raw private keys (`testkey.pk8`) and certificates (`testkey.x509.pem`) are present, the module dynamically compiles them into a PKCS12 keystore (`testkey.p12`) using the Python `cryptography` library.

Once the `.p12` keystore is generated, the raw `.pk8` and `.pem` files are no longer required and can be safely removed from the workspace.
