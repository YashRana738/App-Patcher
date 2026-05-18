# App-Patcher

App-Patcher is a modular configuration-driven framework for modifying Android APKs. It handles decompilation, patching (manifests, resources, and Smali bytecode), class injection, repacking, and signing through a unified pipeline. 

For comprehensive details on creating patches, configuring regular expressions, and managing signing keys, refer to the [Patch Building Guide](docs/patch_building.md).

## Quick Start

### 1. Requirements
Ensure Python 3.8+ is installed. The framework includes a bundled Java runtime environment (JRE) and required standard tools.
```bash
pip install -r requirements.txt
```

### 2. Preparation
Place the target APK file in the input directory:
```text
workspace/input/Gallery_2.9.1.0514.apk
```

### 3. Build Patches
Whenever modifications are made to the source patches in the `patches/` directory, compile them using the patch builder:
```bash
python patch_builder.py
```

### 4. Execute Pipeline
Run `porter.py` to process the APK based on the compiled configurations:
```bash
# Standard execution (decode, patch, build, and sign)
python porter.py

# Dry run (decodes and patches in-memory without building the APK)
python porter.py --dry-run

# Verbose output for debugging
python porter.py --verbose

# Retain the build directory for manual inspection
python porter.py --keep-build
```

### 5. Output
The processed APK will be output to the workspace directory:
```text
workspace/output/Gallery_2.9.1.0514_ported_signed.apk
```

## Repository Structure

```text
App-Patcher/
├── bin/                             # Framework internals and compiled artifacts
│   ├── modules/                     # Core execution modules
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
│   ├── input/                       # Source APK directory
│   ├── keys/                        # Signing keystores and certificates
│   └── output/                      # Final output directory
│
├── README.md                        
├── patch_builder.py                 # Compiles source patches into deployable JSON configurations
└── porter.py                        # Orchestrator script for the patching pipeline
```

## Command-Line Interface

| Argument | Short | Description |
|----------|-------|-------------|
| `--input` | `-i` | Path to the input APK. |
| `--config` | `-c` | Path to the patch configuration index (default: `bin/patches/config/patches.json`). |
| `--output` | `-o` | Path for the output APK. |
| `--dry-run` | | Decode and apply patches in-memory for verification purposes. |
| `--keep-build` | | Prevent deletion of the decoded APK directory after execution. |
| `--verbose` | `-v` | Enable DEBUG level logging. |
| `--no-sign` | | Skip the APK signing phase. |
