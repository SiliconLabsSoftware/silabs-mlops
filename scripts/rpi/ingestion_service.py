import os
import sys

import sequential_ingestion_engine

# Variables required by sequential_ingestion_engine (and batch variant).
_REQUIRED_ENV_VARS = (
    "ZEROBUS_WORKSPACE_URL",
    "ZEROBUS_CLIENT_ID",
    "ZEROBUS_CLIENT_SECRET",
    "ZEROBUS_SERVER_ENDPOINT",
    "ZEROBUS_TABLE_NAME",
    "DATABRICKS_VOLUME_PATH",
    "AUDIO_SAMPLES_DIR",
)

_ENV_FILE_EXAMPLE = """# Example .env structure — replace placeholders with your values; do not commit secrets.
DATABRICKS_VOLUME_PATH=/Volumes/<catalog>/<schema>/<volume>
ZEROBUS_SERVER_ENDPOINT=<workspace-id>.zerobus.<region>.azuredatabricks.net
ZEROBUS_WORKSPACE_URL=https://adb-<workspace-id>.<shard>.azuredatabricks.net
ZEROBUS_TABLE_NAME=<catalog>.<schema>.<table_name>
ZEROBUS_CLIENT_ID=<service-principal-client-id>
ZEROBUS_CLIENT_SECRET=<service-principal-client-secret>
AUDIO_SAMPLES_DIR=/path/to/your/audio_samples
"""


def _ensure_required_env() -> None:
    missing = [
        name for name in _REQUIRED_ENV_VARS if not (os.environ.get(name) or "").strip()
    ]
    if not missing:
        return
    listed = "\n".join(f"  - {name}" for name in missing)
    msg = (
        "Missing or empty required environment variables:\n"
        f"{listed}\n\n"
        "Set them in your environment before running this script (for example, "
        "from a project `.env` file without editing this script):\n"
        "  set -a && source /path/to/repo/.env && set +a\n"
        "  python scripts/rpi/ingestion_service.py\n\n"
        "Expected `.env` keys and shape (values are examples only):\n"
        f"{_ENV_FILE_EXAMPLE}"
    )
    print(msg, file=sys.stderr)
    sys.exit(1)


_ensure_required_env()

# ========================
# Run the Ingestor
# ========================
# Option 1: Standard Ingestion (Processes & uploads one file at a time)

# Option 2: High-Volume Simultaneous Ingestion (Processes & uploads multiple files at once)
# (Uncomment the line below and comment Option 1 to enable parallel uploading)
# import batch_ingestion_engine as sequential_ingestion_engine

if __name__ == "__main__":
    sequential_ingestion_engine.main()
