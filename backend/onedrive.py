"""
OneDrive (Microsoft Graph) integration for automatic stock-list sync.

Uses the OAuth "device code" flow: no redirect URL is needed (handy for a
Streamlit app whose public URL can change), the user just visits a short
Microsoft URL once and enters a code. The resulting refresh token is
stored in the `settings` table and silently renewed after that, so the
warehouse's stock list can be re-pulled from OneDrive automatically
without any further manual steps.

The client id below is the SAME public (non-secret) Microsoft Graph app
registration this warehouse's existing "Slitter" Streamlit app already
uses to read this exact OneDrive file - reusing it means no new Azure AD
app registration is needed. A public client id is not a secret; it's
safe to embed in client code (this is the standard "native/public
client" OAuth pattern), same as any installed desktop or mobile app.

NOTE: this module cannot be exercised from a network-sandboxed dev
environment (no route to login.microsoftonline.com / graph.microsoft.com
here). It's written to be tested once actually deployed with real
internet access - `verify_setup()` is provided to sanity-check the
connection from the Import Stock page.
"""

import base64
import time
from typing import Optional

import requests

from backend import models

CLIENT_ID = "9fdf6ef7-4337-47e5-ba7f-c1a9c680879b"
TENANT = "consumers"
SCOPE = "Files.Read offline_access"

AUTH_BASE = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SETTING_REFRESH_TOKEN = "onedrive_refresh_token"
SETTING_SHARE_URL = "onedrive_share_url"
SETTING_LAST_SYNC_AT = "onedrive_last_sync_at"
SETTING_LAST_SYNC_ETAG = "onedrive_last_sync_etag"
SETTING_LAST_SYNC_ERROR = "onedrive_last_sync_error"
SETTING_AUTO_SYNC_ENABLED = "onedrive_auto_sync_enabled"
SETTING_SYNC_INTERVAL_SECONDS = "onedrive_sync_interval_seconds"

DEFAULT_SYNC_INTERVAL_SECONDS = 300


class OneDriveError(Exception):
    pass


def is_connected() -> bool:
    return bool(models.get_setting(SETTING_REFRESH_TOKEN))


def disconnect() -> None:
    models.delete_setting(SETTING_REFRESH_TOKEN)
    models.delete_setting(SETTING_LAST_SYNC_ETAG)
    models.delete_setting(SETTING_LAST_SYNC_ERROR)


def start_device_flow() -> dict:
    """Kicks off the device-code flow. Returns the dict with
    `user_code`, `verification_uri`, `device_code`, `interval`,
    `expires_in`, `message` - show `message` (or user_code +
    verification_uri) to the user."""
    resp = requests.post(
        f"{AUTH_BASE}/devicecode",
        data={"client_id": CLIENT_ID, "scope": SCOPE},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def poll_device_flow(device_code: str, interval: int, expires_in: int) -> dict:
    """Polls the token endpoint until the user completes sign-in, or the
    code expires. Returns the token response dict on success. Raises
    OneDriveError on failure/timeout."""
    deadline = time.time() + expires_in
    wait = max(interval, 5)

    while time.time() < deadline:
        time.sleep(wait)
        resp = requests.post(
            f"{AUTH_BASE}/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            timeout=30,
        )
        data = resp.json()
        if resp.status_code == 200:
            return data
        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            wait += 5
            continue
        raise OneDriveError(data.get("error_description") or error or "Sign-in failed.")

    raise OneDriveError("Sign-in timed out - please try connecting again.")


def complete_device_flow(token_response: dict) -> None:
    refresh_token = token_response.get("refresh_token")
    if not refresh_token:
        raise OneDriveError("Microsoft did not return a refresh token (check the app's offline_access scope).")
    models.set_setting(SETTING_REFRESH_TOKEN, refresh_token)

    # Best-effort: back the connection up to GitHub right away (if
    # configured) so a later reboot on a host with no persistent storage
    # mount doesn't force reconnecting. Never let this fail the actual
    # connect step the user is waiting on.
    try:
        from backend import github_backup
        github_backup.backup_settings()
    except Exception:
        pass


def get_access_token() -> str:
    refresh_token = models.get_setting(SETTING_REFRESH_TOKEN)
    if not refresh_token:
        raise OneDriveError("OneDrive is not connected yet.")

    resp = requests.post(
        f"{AUTH_BASE}/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPE,
        },
        timeout=30,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise OneDriveError(data.get("error_description") or data.get("error") or "Could not refresh access token.")

    # Microsoft may rotate the refresh token; persist the new one if given.
    if data.get("refresh_token"):
        models.set_setting(SETTING_REFRESH_TOKEN, data["refresh_token"])

    return data["access_token"]


def _resolve_sharing_url(access_token: str, sharing_url: str) -> tuple:
    clean = sharing_url.split("?")[0]
    encoded = base64.urlsafe_b64encode(clean.encode()).decode().rstrip("=")
    resp = requests.get(
        f"{GRAPH_BASE}/shares/u!{encoded}/driveItem",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    item = resp.json()
    return item["id"], item.get("parentReference", {}).get("driveId"), item.get("eTag")


def _download(access_token: str, item_id: str, drive_id: Optional[str]) -> bytes:
    base = f"{GRAPH_BASE}/drives/{drive_id}" if drive_id else f"{GRAPH_BASE}/me/drive"
    resp = requests.get(
        f"{base}/items/{item_id}/content",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=120,
        allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.content


def fetch_latest_stock_bytes(sharing_url: str) -> tuple:
    """Returns (file_bytes, etag). Raises OneDriveError on any failure."""
    try:
        access_token = get_access_token()
        item_id, drive_id, etag = _resolve_sharing_url(access_token, sharing_url)
        content = _download(access_token, item_id, drive_id)
        return content, etag
    except OneDriveError:
        raise
    except requests.RequestException as e:
        raise OneDriveError(f"Network error talking to OneDrive: {e}")
    except Exception as e:
        raise OneDriveError(f"Could not fetch the file from OneDrive: {e}")


def verify_setup(sharing_url: str) -> str:
    """Does a lightweight round-trip (resolve + fetch) to confirm the
    connection actually works, without importing anything. Returns a
    human-readable success message; raises OneDriveError on failure."""
    content, etag = fetch_latest_stock_bytes(sharing_url)
    size_kb = len(content) / 1024
    return f"Connected — downloaded {size_kb:.1f} KB (etag {etag or 'n/a'})."
