"""
validators.py - Common Sanity Checks for SiLabs MLOps
------------------------------------------------------
Provides reusable validation utilities for:
  - IP Address format validation
  - Simplicity Commander path verification
  - Model URI format checks
"""
import re
import os
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IP Address Validation
# ---------------------------------------------------------------------------

_IPV4_PATTERN = re.compile(
    r"^"
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."  # octet 1
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."  # octet 2
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."  # octet 3
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"    # octet 4
    r"$"
)


def is_valid_ipv4(ip: str) -> bool:
    """
    Returns True if 'ip' is a valid IPv4 address, False otherwise.

    Examples:
        >>> is_valid_ipv4("192.168.1.100")   # True
        >>> is_valid_ipv4("999.999.999.999") # False
        >>> is_valid_ipv4("not-an-ip")       # False
    """
    return bool(_IPV4_PATTERN.match(ip.strip()))


def validate_device_ip(ip: Optional[str]) -> Optional[str]:
    """
    Validates and returns the device IP address.

    Args:
        ip: IP address string to validate.

    Returns:
        The validated IP string (stripped of whitespace).

    Raises:
        ValueError: If the IP address format is invalid, with an actionable message.
    """
    if ip is None:
        return None  # device_ip is optional, None means no target IP

    ip = ip.strip()
    if not is_valid_ipv4(ip):
        raise ValueError(
            f"[Validation Error] '{ip}' is not a valid IPv4 address.\n"
            "  Expected format : 192.168.x.x  (e.g. 192.168.1.100)\n"
            "  How to fix      : Use the --ip flag with a valid IP address.\n"
            "                    Example: silabs-mlops model deploy --ip 192.168.1.100 ..."
        )
    logger.debug(f"Device IP validated: {ip}")
    return ip


# ---------------------------------------------------------------------------
# Simplicity Commander Path Validation
# ---------------------------------------------------------------------------

# Default discovery paths per OS
_COMMANDER_DISCOVERY_PATHS_WINDOWS = [
    r"C:\SiliconLabs\SimplicityStudio\v5\developer\adapter_packs\commander\commander.exe",
    r"C:\SiliconLabs\SimplicityStudio\v4\developer\adapter_packs\commander\commander.exe",
]

_COMMANDER_DISCOVERY_PATHS_LINUX = [
    "/usr/local/bin/commander",
    "/usr/bin/commander",
    os.path.expanduser("~/SimplicityCommander-Linux/commander"),
]


def resolve_commander_path(commander_path: Optional[str] = "commander") -> str:
    """
    Resolves the Simplicity Commander executable path.

    Resolution order:
      1. If the provided path is directly executable (in PATH or full path) → use it.
      2. Auto-discover in OS-specific standard directories.
      3. Raise a clear error with actionable instructions if not found.

    Args:
        commander_path: Provided path (from CLI --commander flag or DeployConfig).

    Returns:
        Resolved absolute path to the Simplicity Commander executable.

    Raises:
        FileNotFoundError: With actionable steps if Commander cannot be found.
    """
    # 1. Check if already resolvable (in PATH or full path given)
    if commander_path and shutil.which(commander_path):
        logger.info(f"Simplicity Commander found: {commander_path}")
        return commander_path

    # 2. Auto-discover based on OS
    search_paths = (
        _COMMANDER_DISCOVERY_PATHS_WINDOWS if os.name == "nt"
        else _COMMANDER_DISCOVERY_PATHS_LINUX
    )

    for path in search_paths:
        if os.path.exists(path):
            logger.info(f"Auto-discovered Simplicity Commander at: {path}")
            return path

    # 3. Not found anywhere — raise with helpful message
    platform_hint = (
        "  Windows: Add 'commander.exe' to your PATH, or provide its full path.\n"
        "           Download Simplicity Commander from:\n"
        "           https://www.silabs.com/developers/simplicity-studio\n"
        "  Tip    : Use --commander flag:\n"
        r"           silabs-mlops model deploy --commander 'C:\path\to\commander.exe' ..."
    ) if os.name == "nt" else (
        "  Linux  : Add 'commander' to your PATH, or provide its full path.\n"
        "           Download Simplicity Commander for Linux from:\n"
        "           https://www.silabs.com/developers/simplicity-studio\n"
        "  Tip    : Use --commander flag:\n"
        "           silabs-mlops model deploy --commander '/path/to/commander' ..."
    )

    raise FileNotFoundError(
        f"\n[Validation Error] Simplicity Commander not found.\n"
        f"  Searched in: {search_paths}\n\n"
        f"{platform_hint}"
    )


# ---------------------------------------------------------------------------
# Model URI Validation
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = ('.s37', '.bin', '.hex', '.tflite')

_VALID_URI_PREFIXES = (
    'models:/',   # MLflow Model Registry
    'runs:/',     # MLflow Run artifact
    'http://',    # Direct URL (Databricks Volume etc.)
    'https://',   # Direct URL (Databricks Volume etc.)
)


def validate_model_uri(uri: str) -> str:
    """
    Validates the model URI format.

    Accepts:
      - Local paths ending in a supported extension (.s37, .bin, .hex, .tflite)
      - MLflow Model Registry URIs  (models:/name/version)
      - MLflow Run artifact URIs    (runs:/run_id/path)
      - Direct HTTP/HTTPS URLs

    Args:
        uri: The model URI string to validate.

    Returns:
        The validated URI.

    Raises:
        ValueError: If the URI is empty or unrecognisable.
    """
    if not uri or not uri.strip():
        raise ValueError(
            "[Validation Error] model_uri cannot be empty.\n"
            "  Provide one of:\n"
            "    - A local file path   : ./model.tflite\n"
            "    - An MLflow URI       : models:/my_model/1\n"
            "    - A Databricks Volume : https://<host>/api/2.0/fs/files/Volumes/..."
        )

    uri = uri.strip()

    # Local path: exists on disk
    if os.path.exists(uri):
        return uri

    # Known URI prefix
    if uri.startswith(_VALID_URI_PREFIXES):
        return uri

    # Bare local path that doesn't exist yet
    if any(uri.lower().endswith(ext) for ext in _SUPPORTED_EXTENSIONS):
        return uri

    raise ValueError(
        f"[Validation Error] Unrecognised model_uri format: '{uri}'\n"
        "  Supported formats:\n"
        "    - Local file                : /path/to/model.tflite\n"
        "    - MLflow Model Registry     : models:/model_name/version\n"
        "    - MLflow Run artifact       : runs:/run_id/relative/path\n"
        "    - Databricks Volume URL     : https://<host>/api/2.0/fs/files/Volumes/..."
    )
