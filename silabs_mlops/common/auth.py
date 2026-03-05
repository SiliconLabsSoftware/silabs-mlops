"""
auth.py - Databricks Authentication Helper
-------------------------------------------
Supports two authentication methods:
  1. Personal Access Token (PAT)  → DATABRICKS_TOKEN env var
  2. Service Principal OAuth M2M  → DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET env vars

Resolution order:
  PAT takes priority. If not set, falls back to OAuth M2M using Client ID/Secret.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)


def get_databricks_token(host: str) -> str:
    """
    Resolves a valid Databricks Bearer token using the available credentials.

    Resolution order:
      1. DATABRICKS_TOKEN (Personal Access Token) — used directly if set.
      2. DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET — exchange for OAuth token.

    Args:
        host: The Databricks workspace URL (e.g. https://dbc-xxx.cloud.databricks.com).
              Required for OAuth M2M token exchange.

    Returns:
        A valid Bearer token string.

    Raises:
        EnvironmentError: If no credentials are configured.
        PermissionError: If the token exchange fails.
    """
    # --- Method 1: PAT ---
    pat = os.getenv("DATABRICKS_TOKEN", "").strip()
    if pat:
        logger.info("Using Personal Access Token (DATABRICKS_TOKEN) for authentication.")
        return pat

    # --- Method 2: Service Principal OAuth M2M ---
    client_id     = os.getenv("DATABRICKS_CLIENT_ID", "").strip()
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET", "").strip()

    if client_id and client_secret:
        logger.info("DATABRICKS_TOKEN not set. Attempting OAuth M2M using Client ID/Secret...")
        return _exchange_client_credentials(host, client_id, client_secret)

    # --- No credentials found ---
    raise EnvironmentError(
        "[Auth Error] No Databricks credentials configured.\n"
        "  Option 1 (PAT):                Set DATABRICKS_TOKEN in your .env file.\n"
        "  Option 2 (Service Principal):  Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in your .env file."
    )


def _exchange_client_credentials(host: str, client_id: str, client_secret: str) -> str:
    """
    Exchanges a Service Principal's Client ID and Secret for an OAuth Bearer token
    via Databricks' OIDC M2M endpoint.

    Args:
        host:          Databricks workspace URL.
        client_id:     Service Principal client ID (UUID).
        client_secret: Service Principal client secret.

    Returns:
        A short-lived OAuth Bearer token string.

    Raises:
        PermissionError: If the token exchange is rejected.
        RuntimeError:    On unexpected HTTP errors.
    """
    token_url = f"{host.rstrip('/')}/oidc/v1/token"

    logger.info(f"Requesting OAuth token from: {token_url}")

    response = requests.post(
        token_url,
        data={
            "grant_type":    "client_credentials",
            "scope":         "all-apis",
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code == 401:
        raise PermissionError(
            "[Auth Error] OAuth token exchange failed (HTTP 401).\n"
            "  Your Client ID or Client Secret may be incorrect.\n"
            "  Check DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in your .env file."
        )
    if response.status_code == 403:
        raise PermissionError(
            "[Auth Error] OAuth token exchange forbidden (HTTP 403).\n"
            "  Ensure your Service Principal has the required workspace permissions."
        )

    if not response.ok:
        raise RuntimeError(
            f"[Auth Error] Unexpected error during OAuth token exchange (HTTP {response.status_code}).\n"
            f"  Response: {response.text}"
        )

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError(
            "[Auth Error] Token exchange succeeded but 'access_token' was missing in the response.\n"
            f"  Response: {response.json()}"
        )

    logger.info("OAuth token obtained successfully.")
    return token
