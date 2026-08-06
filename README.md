# Nothing Gallery Port for Non-Nothing OS Devices

This repository contains the official **App-Patcher** port configuration and automated pipeline for **Nothing Gallery** (`com.nothing.gallery`), enabling the full Nothing OS Gallery experience on any Android device (Samsung, Google Pixel, OnePlus, Xiaomi, Motorola, etc.).

---

## Features & Applied Patches

The Nothing Gallery port applies 8 targeted patches to remove vendor restrictions and enable all premium features on non-Nothing hardware:

1. **`[Inject] dependency_patch`**: Injects native `com.nothing.NtFeaturesUtils` and `com.nothing.utils.Utils` dependency stubs to prevent app crashes on generic Android ROMs.
2. **`[Manifest] add_custom_proxy`**: Redirects system service queries to local community stubs.
3. **`[Manifest] add_intent`**: Restores system review/view image intents across non-NOS devices.
4. **`[Res] Add_Link`**: Fixes light/dark theme resource references and UI text.
5. **`[Res] Rename_app`**: Corrects app naming and branding strings.
6. **`[Smali] Force_Media_Taken_By_Nothing`**: Enables Nothing Camera special features and watermarking for all photos.
7. **`[Smali] Force_Nothing_remove_preinstall`**: Bypasses OS pre-install checks and system signature requirements.
8. **`[Smali] Rename_Proxy`**: Rewrites proxy calls to use local injected helpers.

---

## How to Get the Ported APK

### Option A: Build Automatically via GitHub Actions (Recommended)

1. Go to the **Actions** tab on this GitHub repository.
2. Click **Build Standalone APK** workflow on the left sidebar.
3. Click **Run workflow**, enter the direct download link for the Nothing Gallery `.apkm` / `.apks` / `.apk` package (or leave blank if using default in repo).
4. When the build completes, download the **`ported-standalone-apk`** artifact zip containing your installation-ready `.apk`.

---

### Option B: Build Locally

#### 1. Setup Environment
- Install Python 3.8+ and JDK 17+.
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

#### 2. Place Nothing Gallery Bundle
Place your Nothing Gallery bundle (`.apkm` / `.apks` / `.apk`) into `workspace/input/`:
```text
workspace/input/com.nothing.gallery_3.1.0.0723-301000.apkm
```

#### 3. Build the Ported APK
```bash
# Step 1: Compile patch files into deployment config
python patch_builder.py

# Step 2: Convert bundle, apply patches, repack, and sign
python porter.py
```

Your ported APK will be output to:
```text
workspace/output/com.nothing.gallery_3.1.0.0723-301000_ported_signed.apk
```

---

## Requirements

- **Target Device OS:** Android 12.0 (API 31) or higher.
- **Supported Devices:** Any Android smartphone (Google Pixel, Samsung Galaxy, OnePlus, Xiaomi, Motorola, ROG, etc.).

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

## Legal & Trademark Disclaimer

> [!IMPORTANT]
> **Trademark Notice:**
> **Nothing**, **Nothing OS**, **Nothing Gallery**, and all associated logos, icons, and software components are registered trademarks of **Nothing Technology Limited**.
>
> This project is an independent community port created strictly for research, educational, and interoperability purposes. It is **not** affiliated with, sponsored, or endorsed by Nothing Technology Limited.
