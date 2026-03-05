"""Model Deployment to Silicon Labs Devices."""
import subprocess
import logging
import os
import shutil
import tempfile
import mlflow
from silabs_mlops.model.config import DeployConfig
from silabs_mlops.model.registry import ArtifactRegistry, is_artifact_name
from silabs_mlops.common.validators import (
    validate_device_ip,
    validate_model_uri,
    resolve_commander_path,
)
from silabs_mlops.common.auth import get_databricks_token

logger = logging.getLogger(__name__)

# Supported firmware/model file extensions
_SUPPORTED_EXTENSIONS = ('.s37', '.bin', '.hex', '.tflite')


class ModelDeployer:
    """
    Orchestrates model deployment to Silicon Labs embedded devices.

    Workflow:
        1. Validate all inputs (URI, IP, Commander path).
        2. Download the model artifact from the appropriate source.
        3. Flash the artifact to the target device using Simplicity Commander.
    """

    def __init__(self, config: DeployConfig):
        """
        Initialize and validate the deployment configuration.

        Args:
            config: DeployConfig object containing all deployment settings.

        Raises:
            ValueError: If any config field fails validation.
            FileNotFoundError: If Simplicity Commander cannot be found.
        """
        self.config = config
        self._validate_config()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_config(self):
        """Runs all sanity checks on the configuration before deployment."""
        logger.info("Validating deployment configuration...")

        self.config.model_uri = self._resolve_artifact_name(self.config.model_uri)
        self.config.model_uri = validate_model_uri(self.config.model_uri)
        self.config.device_ip = validate_device_ip(self.config.device_ip)
        self.config.commander_path = resolve_commander_path(self.config.commander_path)

        logger.info("Configuration validated successfully.")

    # ------------------------------------------------------------------
    # Artifact Registry Resolver
    # ------------------------------------------------------------------

    def _resolve_artifact_name(self, uri: str) -> str:
        """
        If the user provided a short artifact name (e.g. 'iot_model'),
        look it up in artifacts.yaml and return the full Databricks URL.

        If the URI is already a full path (http/https, models:/, local path),
        it is returned unchanged.

        Args:
            uri: A short artifact name or a full model URI.

        Returns:
            A fully-qualified URI ready for downloading.
        """
        if not is_artifact_name(uri):
            return uri  # Already a full URI / local path — pass through unchanged

        logger.info(f"Short artifact name detected: '{uri}'. Resolving via registry...")
        registry = ArtifactRegistry()
        resolved = registry.resolve(uri)
        return resolved

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deploy(self):
        """
        Orchestrates the full deployment process:
          1. Download model artifact to a secure temp directory.
          2. Flash it to the target device via Simplicity Commander.
          3. Always clean up the temp directory afterwards (success or failure).


        Raises:
            Exception: Re-raises any exception from download or flash steps.
        """
        logger.info(f"Starting deployment for model URI: {self.config.model_uri}")

        tmp_dir = tempfile.mkdtemp(prefix="silabs_mlops_deploy_")
        logger.info(f"Temporary working directory: {tmp_dir}")

        try:
            model_path = self._download_model(tmp_dir=tmp_dir)
            logger.info(f"Model ready at: {model_path}")

            self._flash_model(model_path)
            logger.info("Deployment completed successfully.")

        except Exception:
            raise

        finally:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.info(f"Temporary files cleaned up: {tmp_dir}")

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _download_model(self, tmp_dir: str) -> str:
        """
        Downloads the model artifact from the appropriate source.

        Resolution order:
          1. Local path (already on disk) → use as-is (never deleted).
          2. HTTP/HTTPS URL (Databricks Volume) → download into tmp_dir.
          3. MLflow URI (models:/ or runs:/) → download into tmp_dir via MLflow.

        Args:
            tmp_dir: Secure temporary directory where downloads are stored.

        Returns:
            Absolute local path to the model file.

        Raises:
            FileNotFoundError: If no supported firmware file is found.
        """
        logger.info(f"Downloading model from: {self.config.model_uri}")

        try:
            if os.path.exists(self.config.model_uri):
                logger.info("Using local model file.")
                return self.config.model_uri

            if self.config.model_uri.startswith(('http://', 'https://')):
                return self._download_from_url(self.config.model_uri, dest_dir=tmp_dir)

            local_path = mlflow.artifacts.download_artifacts(
                artifact_uri=self.config.model_uri,
                dst_path=tmp_dir
            )

            if os.path.isdir(local_path):
                return self._find_firmware_in_dir(local_path)

            return local_path

        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise

    def _download_from_url(self, url: str, dest_dir: str) -> str:
        """
        Downloads a file from a direct URL (e.g. Databricks Volume).
        Uses DATABRICKS_TOKEN env var for auth if available.

        Args:
            url: HTTP/HTTPS URL to the model file.
            dest_dir: Directory where the downloaded file is saved.

        Returns:
            Absolute local path to the downloaded file.

        Raises:
            requests.HTTPError: If the server returns a non-2xx status code.
        """
        import requests

        host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
        try:
            token = get_databricks_token(host)
            headers = {"Authorization": f"Bearer {token}"}
        except EnvironmentError:
            logger.warning("No Databricks credentials found. Attempting unauthenticated download.")
            headers = {}

        filename = url.split("/")[-1]
        local_path = os.path.join(dest_dir, filename)

        logger.info(f"Downloading to: {local_path}")
        response = requests.get(url, headers=headers, stream=True)

        if response.status_code == 401:
            raise PermissionError(
                "[Download Error] Authentication failed (HTTP 401).\n"
                "  Ensure DATABRICKS_TOKEN is set in your environment.\n"
                "  Example: set DATABRICKS_TOKEN=dapi..."
            )
        if response.status_code == 403:
            raise PermissionError(
                "[Download Error] Access denied (HTTP 403).\n"
                "  Your token may not have READ permission on this Volume.\n"
                "  Check Unity Catalog permissions for the target Volume."
            )
        if response.status_code == 404:
            raise FileNotFoundError(
                f"[Download Error] File not found on server (HTTP 404).\n"
                f"  URL: {url}\n"
                "  Verify the Databricks Volume path and file name are correct."
            )

        response.raise_for_status()  # Catch any other HTTP errors

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return local_path

    def _find_firmware_in_dir(self, directory: str) -> str:
        """
        Locates a supported firmware/model file inside a directory.

        Args:
            directory: Path to directory returned by MLflow.

        Returns:
            Absolute path to the firmware file.

        Raises:
            FileNotFoundError: If no supported file is found.
        """
        all_files = os.listdir(directory)
        firmware_files = [f for f in all_files if f.lower().endswith(_SUPPORTED_EXTENSIONS)]

        if not firmware_files:
            raise FileNotFoundError(
                f"[Download Error] No supported firmware file found in MLflow artifact directory.\n"
                f"  Directory : {directory}\n"
                f"  Found     : {all_files}\n"
                f"  Supported : {_SUPPORTED_EXTENSIONS}\n"
                "  Ensure your MLflow model artifact contains a .tflite, .s37, .bin, or .hex file."
            )

        if len(firmware_files) > 1:
            logger.warning(
                f"Multiple firmware files found: {firmware_files}. "
                f"Using the first one: {firmware_files[0]}"
            )

        return os.path.join(directory, firmware_files[0])

    def _flash_model(self, model_path: str):
        """
        Executes Simplicity Commander to flash the model to the device.

        Args:
            model_path: Local path to the firmware/model file to flash.

        Raises:
            RuntimeError: If Commander returns a non-zero exit code.
        """
        logger.info("Flashing model to device via Simplicity Commander...")

        command = [self.config.commander_path, "flash", model_path]

        if self.config.device_ip:
            command.extend(["--ip", self.config.device_ip])

        if self.config.noverify:
            command.append("--noverify")
        elif self.config.verify:
            command.append("--verify")

        if self.config.halt:
            command.append("--halt")

        logger.info(f"Executing: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"Commander Output:\n{result.stdout}")

        except subprocess.CalledProcessError as e:
            commander_output = e.stderr.strip() if e.stderr else None

            if commander_output:
                user_message = (
                    f"Simplicity Commander failed (exit code {e.returncode}).\n"
                    f"  Commander said: {commander_output}"
                )
            else:
                # No output from Commander — common when device is unreachable
                user_message = (
                    f"Simplicity Commander could not reach the device (exit code {e.returncode}).\n"
                    "  This usually means the device is not connected or the IP is incorrect.\n"
                    f"  Device IP   : {self.config.device_ip or 'not specified'}\n"
                    "  Next step   : Connect the device and verify the IP is reachable."
                )

            raise RuntimeError(user_message)
