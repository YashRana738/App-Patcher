# App-Patcher

App-Patcher is a modular, configuration-driven framework for modifying Android APKs and APKS/XAPK/APKM split packages. It handles decompilation, manifest modification, resource adjustments, Smali bytecode patching, class injection, repacking, and signing through a unified, automated pipeline.

Outputs are automatically converted and repackaged into a **single standalone signed `.apk` file** ready for installation.

For comprehensive details on creating patches, configuring regular expressions, and managing signing keys, refer to the [Patch Building Guide](docs/patch_building.md).

---

## Quick Start

### 1. Requirements
Ensure Python 3.8+ and Java (System JVM JDK 17+) are available.
```bash
pip install -r requirements.txt
```

### 2. Preparation
Place the target `.apk`, `.apks`, `.xapk`, or `.apkm` package in the input directory:
```text
workspace/input/com.nothing.gallery_3.1.0.0723-301000.apkm
```

### 3. Build Patches
Compile source patch definitions from `patches/`:
```bash
python patch_builder.py
```

### 4. Execute Pipeline
Run `porter.py` to process the package into a single standalone `.apk`:
```bash
# Standard execution (decode, patch, build single APK, and sign)
python porter.py

# Process a specific package
python porter.py -i workspace/input/App_Bundle.apkm

# Dry run mode (validates patches in-memory without building)
python porter.py --dry-run
```

### 5. Output
The final standalone APK will be output to:
```text
workspace/output/com.nothing.gallery_3.1.0.0723-301000_ported_signed.apk
```

---

## GitHub Actions & Automated Releases

This repository includes a GitHub Actions workflow (`.github/workflows/build.yml`) that automatically builds, patches, and publishes ported APK releases.

### How GitHub Releases & CI Work:
1. **Push & Tag Triggers:** Whenever code is pushed to `main` or `nothing_gallery`, GitHub Actions runs the patch builder and porter pipeline.
2. **Automated Release Publishing:** When a release tag (e.g. `v1.0.0`) is pushed or manually triggered via **Workflow Dispatch**, GitHub Actions automatically compiles the single `.apk` file and publishes it directly to **GitHub Releases**.
3. **Remote Package URLs:** You can trigger a build on GitHub Actions by supplying a direct URL to an `.apk` / `.apkm` file in the workflow dispatch inputs.

---

## Repository Structure

```text
App-Patcher/
├── .github/
│   └── workflows/
│       └── build.yml                # CI/CD pipeline & automated release publisher
│
├── bin/                             # Framework internals and compiled artifacts
│   ├── modules/                     # Core execution modules (decompilation, APKS resolution, patching, signing)
│   ├── patches/                     # Compiled JSON patch definitions
│   │   └── config/                  # Global build configurations and patch indices
│   └── tools/                       # Bundled CLI utilities (apktool, baksmali, smali, ubersigner)
│
├── docs/                            # Documentation
│   └── patch_building.md            # Reference guide for patch creation
│
├── logs/                            # Execution logs
│
├── patches/                         # Source patch definitions (User-editable)
│   ├── [Inject] dependency_patch/   
│   ├── [Manifest] add_custom_proxy/ 
│   ├── [Res] Add_Link/              
│   ├── [Smali] Rename_Proxy/        
│   └── ...
│
├── workspace/                       # Execution environment
│   ├── input/                       # Source APK / APKS / APKM directory
│   ├── keys/                        # Signing keystores and certificates
│   └── output/                      # Final output directory (single standalone .apk)
│
├── LICENSE                          # Open source license
├── README.md                        
├── patch_builder.py                 # Compiles source patches into deployable JSON configurations
└── porter.py                        # Orchestrator script for the patching pipeline
```

---

## Command-Line Interface

| Argument | Short | Description |
|----------|-------|-------------|
| `--input` | `-i` | Path to the input APK, APKS, XAPK, or APKM package. |
| `--config` | `-c` | Path to the patch configuration index (default: `bin/patches/config/patches.json`). |
| `--output` | `-o` | Path for the final standalone output APK file. |
| `--dry-run` | | Decode and apply patches in-memory for verification purposes. |
| `--keep-build` | | Prevent deletion of the decoded APK directory after execution. |
| `--verbose` | `-v` | Enable DEBUG level logging. |
| `--no-sign` | | Skip the APK signing phase. |

---

## Legal & Trademark Disclaimer

> [!IMPORTANT]
> **Trademark Notice:**
> **Nothing**, **Nothing OS**, **Nothing Gallery**, and all associated brand names, logos, assets, and software components are registered trademarks and intellectual property reserved by **Nothing Technology Limited**.
>
> **App-Patcher** is an independent, community-driven framework created strictly for research, portability, educational, and interoperability purposes. This repository is **not affiliated with, authorized, maintained, sponsored, or endorsed** by Nothing Technology Limited or any of its subsidiaries.
