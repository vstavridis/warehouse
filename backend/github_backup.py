"""
Backs up the OneDrive connection (refresh token + sync settings) to a
GitHub repo, so it survives a container reboot/redeploy even on hosts
with no persistent storage mount at all - not just the ones
config._resolve_persistent_root() can find. This mirrors the same
approach this warehouse's existing "Slitter" Streamlit app already uses
for its own database backups (writing a small file to a repo via the
GitHub Contents API, and restoring the latest version on startup),
scoped down here to just the handful of small settings that actually
need to survive a reboot - not the whole database, which stays local
(and, when available, on the persistent storage path already set up).

Requires repo secrets/env vars (checked in this order, so an app that
already has Slitter's secrets configured can reuse them for free):
    WAREHOUSE_GITHUB_TOKEN / QUEUE_GITHUB_TOKEN / DISPLAY_GITHUB_TOKEN
    WAREHOUSE_GITHUB_REPO  / QUEUE_GITHUB_REPO  / DISPLAY_GITHUB_REPO
    WAREHOUSE_GITHUB_BRANCH / QUEUE_GITHUB_BRANCH / DISPLAY_GITHUB_BRANCH (default "main")
The token needs "contents: write" access to that repo (a classic PAT
with the "repo" scope, or a fine-grained PAT scoped to it, both work).

NOTE: this was written and its HTTP mechanics verified against the
public, unauthenticated GitHub API from this dev sandbox (api.github.com
is reachable here) - the authenticated write path needs a real token to
fully verify, which isn't available in this environment.
"""

import base64
import json
from typing import Optional

import requests

from backend import models

BACKUP_PATH = "warehouse_data/onedrive_settings.json"
API_BASE = "https://api.github.com"

BACKED_UP_KEYS = [
    "onedrive_refresh_token",
    "onedrive_share_url",
    "onedrive_auto_sync_enabled",
    "onedrive_sync_interval_seconds",
]


class GitHubBackupError(Exception):
    pass


def _secret(*names: str) -> str:
    for name in names:
        try:
            import streamlit as st
            value = str(st.secrets.get(name, "")).strip()
        except Exception:
            value = ""
        if not value:
            import os
            value = str(os.getenv(name, "")).strip()
        if value:
            return value
    return ""


def _token() -> str:
    return _secret("WAREHOUSE_GITHUB_TOKEN", "QUEUE_GITHUB_TOKEN", "DISPLAY_GITHUB_TOKEN")


def _repo() -> str:
    return _secret("WAREHOUSE_GITHUB_REPO", "QUEUE_GITHUB_REPO", "DISPLAY_GITHUB_REPO")


def _branch() -> str:
    return _secret("WAREHOUSE_GITHUB_BRANCH", "QUEUE_GITHUB_BRANCH", "DISPLAY_GITHUB_BRANCH") or "main"


def is_configured() -> bool:
    return bool(_token() and _repo())


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "warehouse-backup",
    }


def backup_settings() -> None:
    """Push the current OneDrive-related settings to GitHub. Silently
    does nothing if no repo/token is configured; raises GitHubBackupError
    on an actual API failure so callers can decide whether to surface it."""
    if not is_configured():
        return

    token, repo, branch = _token(), _repo(), _branch()
    payload = {key: models.get_setting(key) for key in BACKED_UP_KEYS}
    content_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

    url = f"{API_BASE}/repos/{repo}/contents/{BACKUP_PATH}"
    headers = _headers(token)

    # Need the current file's sha to update it in place; absent on first backup.
    sha = None
    try:
        get_resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
    except requests.RequestException:
        pass

    body = {
        "message": "Update warehouse OneDrive connection backup",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    try:
        put_resp = requests.put(
            url, headers={**headers, "Content-Type": "application/json"},
            data=json.dumps(body), timeout=30,
        )
    except requests.RequestException as e:
        raise GitHubBackupError(f"Network error backing up to GitHub: {e}")

    if put_resp.status_code not in (200, 201):
        raise GitHubBackupError(
            f"GitHub backup failed ({put_resp.status_code}): {put_resp.text[:300]}"
        )


def restore_settings(overwrite: bool = False) -> bool:
    """Pull the OneDrive settings back from GitHub into the local
    settings table. By default only fills in keys that aren't already
    set locally, so it never clobbers a fresher local connection. Returns
    True if anything was restored."""
    if not is_configured():
        return False

    token, repo, branch = _token(), _repo(), _branch()
    url = f"{API_BASE}/repos/{repo}/contents/{BACKUP_PATH}"

    try:
        resp = requests.get(
            url, headers=_headers(token), params={"ref": branch}, timeout=30,
        )
    except requests.RequestException:
        return False

    if resp.status_code != 200:
        return False

    try:
        data = resp.json()
        payload = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    except (KeyError, ValueError, TypeError):
        return False

    restored = False
    for key in BACKED_UP_KEYS:
        value = payload.get(key)
        if value is None:
            continue
        if overwrite or not models.get_setting(key):
            models.set_setting(key, value)
            restored = True
    return restored
