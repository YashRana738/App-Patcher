"""
Signer module — signs an APK using uber-apk-signer.

Handles the output file renaming that uber-apk-signer does
(it appends "-aligned-debugSigned" to the filename).
"""

import os
import glob
from typing import Dict, Optional

from bin.modules import logger
from bin.modules.shell import run_command
from bin.modules.exceptions import SignError


def _get_custom_keystore_args(project_root: str) -> list:
    """
    Check if a custom keystore or pk8/pem pair exists in workspace/keys/.
    If so, compile pk8/pem into a PKCS12 keystore (.p12) if needed, and
    return the command line arguments for uber-apk-signer.
    """
    keys_dir = os.path.join(project_root, "workspace", "keys")
    if not os.path.isdir(keys_dir):
        return []

    # 1. First, check if a compiled PKCS12 keystore (.p12) already exists
    p12_files = [f for f in os.listdir(keys_dir) if f.endswith(".p12")]
    
    if p12_files:
        p12_file = p12_files[0]
        base_name = os.path.splitext(p12_file)[0]
        p12_path = os.path.join(keys_dir, p12_file)
        
        # Check if source pk8/pem keys exist to see if we need to regenerate/update
        pk8_path = os.path.join(keys_dir, f"{base_name}.pk8")
        pem_candidates = [
            f"{base_name}.x509.pem",
            f"{base_name}.pem",
            f"{base_name}.x509",
        ]
        pem_path = None
        for candidate in pem_candidates:
            if os.path.isfile(os.path.join(keys_dir, candidate)):
                pem_path = os.path.join(keys_dir, candidate)
                break

        # If source keys are still present, check if p12 is outdated
        if os.path.isfile(pk8_path) and pem_path:
            if os.path.getmtime(p12_path) < os.path.getmtime(pk8_path) or \
               os.path.getmtime(p12_path) < os.path.getmtime(pem_path):
                logger.info(f"Source keys updated. Regenerating PKCS12 keystore...")
                _generate_p12_keystore(pk8_path, pem_path, p12_path, base_name)
        
        logger.info(f"Using custom keystore for signing: {os.path.basename(p12_path)} (alias: {base_name})")
        return [
            "--ks", p12_path,
            "--ksAlias", base_name,
            "--ksPass", "password",
            "--ksKeyPass", "password"
        ]

    # 2. If no .p12 exists, see if we have .pk8 and matching certificate to compile a new one
    pk8_files = [f for f in os.listdir(keys_dir) if f.endswith(".pk8")]
    if not pk8_files:
        return []

    pk8_file = pk8_files[0]
    base_name = os.path.splitext(pk8_file)[0] # e.g. "testkey"

    # Look for matching PEM certificate (.x509.pem, .pem, or .x509)
    pem_candidates = [
        f"{base_name}.x509.pem",
        f"{base_name}.pem",
        f"{base_name}.x509",
    ]
    pem_file = None
    for candidate in pem_candidates:
        if os.path.isfile(os.path.join(keys_dir, candidate)):
            pem_file = candidate
            break

    if not pem_file:
        logger.warning(f"Found private key {pk8_file} but no matching certificate in {keys_dir}")
        return []

    pk8_path = os.path.join(keys_dir, pk8_file)
    pem_path = os.path.join(keys_dir, pem_file)
    p12_path = os.path.join(keys_dir, f"{base_name}.p12")

    if _generate_p12_keystore(pk8_path, pem_path, p12_path, base_name):
        logger.info(f"Using custom keystore for signing: {os.path.basename(p12_path)} (alias: {base_name})")
        return [
            "--ks", p12_path,
            "--ksAlias", base_name,
            "--ksPass", "password",
            "--ksKeyPass", "password"
        ]

    return []


def _generate_p12_keystore(pk8_path: str, pem_path: str, p12_path: str, base_name: str) -> bool:
    """Generate a PKCS12 (.p12) keystore from pk8 and pem files."""
    logger.info(f"Generating PKCS12 keystore from {os.path.basename(pk8_path)} and {os.path.basename(pem_path)}...")
    try:
        from cryptography.hazmat.primitives.serialization import load_der_private_key
        from cryptography.x509 import load_pem_x509_certificate
        from cryptography.hazmat.primitives.serialization.pkcs12 import serialize_key_and_certificates
        from cryptography.hazmat.primitives.serialization import BestAvailableEncryption

        with open(pk8_path, "rb") as f:
            key_bytes = f.read()
        private_key = load_der_private_key(key_bytes, password=None)

        with open(pem_path, "rb") as f:
            cert_bytes = f.read()
        cert = load_pem_x509_certificate(cert_bytes)

        p12_bytes = serialize_key_and_certificates(
            name=base_name.encode("utf-8"),
            key=private_key,
            cert=cert,
            cas=None,
            encryption_algorithm=BestAvailableEncryption(b"password")
        )

        with open(p12_path, "wb") as f:
            f.write(p12_bytes)
        logger.success(f"Generated keystore successfully: {p12_path}")
        return True

    except ImportError:
        logger.warning(
            "Python 'cryptography' library is required to sign with custom pk8/pem keys. "
            "Run 'pip install cryptography' to enable, or sign with default debug key."
        )
        return False
    except Exception as e:
        logger.error(f"Failed to generate PKCS12 keystore: {e}")
        return False


def sign_apk(
    apk_path: str,
    tools: Dict[str, str],
    project_root: str,
) -> str:
    """
    Sign an APK using uber-apk-signer.

    Args:
        apk_path:     Path to the unsigned APK.
        tools:        Tool paths dict from tools.json.
        project_root: Absolute path to the project root.

    Returns:
        The path to the final signed APK.

    Raises:
        SignError: If signing fails or the signed file isn't found.
    """
    if not os.path.isfile(apk_path):
        raise SignError(f"APK to sign not found: {apk_path}")

    java = os.path.join(project_root, tools["java"])
    ubersigner = os.path.join(project_root, tools["ubersigner"])

    logger.info("Signing APK...")

    cmd = [
        java,
        "-jar",
        ubersigner,
        "--apks",
        apk_path,
    ]

    custom_args = _get_custom_keystore_args(project_root)
    if custom_args:
        cmd.extend(custom_args)

    try:
        run_command(cmd, description="uber-apk-signer")
    except Exception as e:
        raise SignError(f"Failed to sign APK: {e}")

    # uber-apk-signer creates files like:
    #   name-aligned-debugSigned.apk
    #   name-aligned-signed.apk
    # Find the signed output
    signed_apk = _find_signed_apk(apk_path)

    if signed_apk is None:
        raise SignError(
            f"Signing appeared to succeed but no signed APK found. "
            f"Looked for variants of: {apk_path}"
        )

    # Rename to a clean final name
    final_path = _make_final_path(apk_path)
    if signed_apk != final_path:
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(signed_apk, final_path)

    # Delete the unsigned APK now that we have the signed one
    if os.path.exists(apk_path) and apk_path != final_path:
        os.remove(apk_path)
        logger.debug(f"Removed unsigned APK: {os.path.basename(apk_path)}")

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    logger.success(f"APK signed: {final_path} ({size_mb:.1f} MB)")

    # Clean up intermediate files from uber-apk-signer
    _cleanup_signer_artifacts(apk_path, final_path)

    return final_path


def _find_signed_apk(original_path: str) -> Optional[str]:
    """
    Find the signed APK produced by uber-apk-signer.

    It typically adds suffixes like -aligned-debugSigned or -aligned-signed.
    """
    base = original_path.rsplit(".", 1)[0]
    candidates = [
        f"{base}-aligned-debugSigned.apk",
        f"{base}-aligned-signed.apk",
        f"{base}-debugSigned.apk",
        f"{base}-signed.apk",
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Fallback: glob for any *-signed* or *-aligned* variant
    pattern = f"{base}*signed*.apk"
    matches = glob.glob(pattern)
    if matches:
        return matches[0]

    return None


def _make_final_path(original_path: str) -> str:
    """
    Generate a clean final filename from the original APK path.

    e.g. workspace/output/ported.apk → workspace/output/ported-signed.apk
    """
    base, ext = os.path.splitext(original_path)
    return f"{base}_signed{ext}"


def _cleanup_signer_artifacts(original_path: str, final_path: str) -> None:
    """Remove intermediate files created by uber-apk-signer."""
    base = original_path.rsplit(".", 1)[0]
    patterns = [
        f"{base}-aligned-debugSigned.apk",
        f"{base}-aligned-signed.apk",
        f"{base}-debugSigned.apk",
        f"{base}-signed.apk",
        f"{base}.apk.idsig",
    ]

    for pattern in patterns:
        if pattern == final_path:
            continue
        if os.path.isfile(pattern):
            try:
                os.remove(pattern)
                logger.debug(f"Cleaned up: {os.path.basename(pattern)}")
            except OSError:
                pass
