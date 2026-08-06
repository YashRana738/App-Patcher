"""
Custom exception hierarchy for APK Porter.
All exceptions inherit from APKPorterError so callers can catch broadly or narrowly.
"""


class APKPorterError(Exception):
    """Base exception for all APK Porter errors."""
    pass


class ConfigError(APKPorterError):
    """Raised when config files are missing, malformed, or fail validation."""
    pass


class ToolError(APKPorterError):
    """Raised when an external tool (apktool, baksmali, etc.) is missing or fails."""
    pass


class DecodeError(APKPorterError):
    """Raised when APK decoding (unpacking) fails."""
    pass


class ManifestPatchError(APKPorterError):
    """Raised when a manifest patch fails and skip_on_fail is False."""
    pass


class ResourcePatchError(APKPorterError):
    """Raised when a resource patch fails and skip_on_fail is False."""
    pass


class SmaliPatchError(APKPorterError):
    """Raised when a smali/dex patch fails and skip_on_fail is False."""
    pass


class ClassInjectionError(APKPorterError):
    """Raised when class injection fails and skip_on_fail is False."""
    pass


class BuildError(APKPorterError):
    """Raised when APK repacking fails."""
    pass


class SignError(APKPorterError):
    """Raised when APK signing fails."""
    pass


class ValidationError(APKPorterError):
    """Raised when input validation fails (file not found, bad format, etc.)."""
    pass
