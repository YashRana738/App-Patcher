# App-Patcher Framework

**App-Patcher** is a production-grade, modular, configuration-driven Python framework for reverse engineering, patching, and converting Android APKs, APKS, XAPK, APKM, and APK+ split bundles into single standalone signed `.apk` files.

---

## Key Features

- **Split Bundle Merger:** Automatically converts `.apks`, `.xapk`, `.apkm`, and `.apk+` split bundles into a single standalone `.apk` using binary resource table remapping (`APKEditor.jar`) and native ABI/DEX re-indexing.
- **Smali Bytecode Patching:** Find and replace smali instructions across all decompiled DEX trees (`smali/`, `smali_classes2/`, `smali_classes3/`, etc.).
- **Manifest Patching:** Dynamic regex string replacement and XML tag injection into `AndroidManifest.xml`.
- **Resource Modding:** Modify strings, colors, styles, and layout XML files in `res/values/` and subdirectories.
- **Smali Class Injection:** Inject new Smali class trees and utility packages seamlessly.
- **Automated Signing:** Signs output APKs with v1/v2/v3/v4 signatures using `uber-apk-signer` or custom PKCS12 / `.pk8` + `.pem` keys.
- **CI/CD Ready:** Built-in GitHub Actions workflow supporting `workflow_dispatch` with remote package URLs.

---

## Quick Start

### 1. Requirements
- Python 3.8+
- Java (System JDK 17+)
- `pip install -r requirements.txt`

### 2. Basic Usage

Place your target package (`.apk`, `.apks`, `.xapk`, `.apkm`) into `workspace/input/` and run:

```bash
# Decompile, patch, repack, and sign
python porter.py

# Process a specific package file
python porter.py --input workspace/input/sample_app.apkm

# Dry run mode (validate patches without building)
python porter.py --dry-run
```

The final signed standalone `.apk` will be created in `workspace/output/`.

---

## Creating Patches

You can define patches in human-readable plain text format under `patches/` and compile them into JSON deployment configs:

```bash
python patch_builder.py
```

For complete instructions on regex replacement syntax, smali tree injection, and custom keys, see the [Patch Building Guide](docs/patch_building.md).

---

## Repository Layout

```text
App-Patcher/
├── .github/workflows/build.yml     # Automated CI/CD workflow
├── bin/
│   ├── modules/                    # Python core modules (decompilation, APKS resolution, patching, signing)
│   ├── patches/config/             # Target patches configuration index
│   └── tools/                      # CLI tools (apktool, APKEditor, ubersigner)
├── docs/                           # Framework documentation
├── patches/                        # Source patch definitions directory
├── workspace/
│   ├── input/                      # Input package directory
│   ├── keys/                       # Custom keystores (.p12, .pk8, .pem)
│   └── output/                     # Final standalone output APK directory
├── patch_builder.py                # Compiles source patches into JSON definitions
├── porter.py                       # Main CLI pipeline orchestrator
└── README.md
```

---

## Command-Line Options

| Argument | Short | Description |
|----------|-------|-------------|
| `--input` | `-i` | Path to input APK, APKS, XAPK, or APKM package. |
| `--config` | `-c` | Path to patch config index (default: `bin/patches/config/patches.json`). |
| `--output` | `-o` | Path for final standalone output APK file. |
| `--dry-run` | | Decode and apply patches in-memory for verification purposes. |
| `--keep-build` | | Prevent deletion of decoded APK directory after execution. |
| `--verbose` | `-v` | Enable DEBUG level logging. |
| `--no-sign` | | Skip the APK signing phase. |

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more details.
