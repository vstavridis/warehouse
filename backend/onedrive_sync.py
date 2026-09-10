"""
Periodic background sync: re-pulls the stock list from OneDrive on an
interval, so the warehouse app stays current without anyone manually
re-uploading the file. Called from backend.ui.apply_page_chrome() on
every page load - the OneDrive round trip only actually happens when the
configured interval has elapsed, so most page loads just do one cheap
settings read.
"""

import io
from datetime import datetime, timedelta
from typing import Optional

from backend import models
from backend import onedrive
from backend.stock_import import import_stock_from_excel


def _auto_sync_enabled() -> bool:
    return models.get_setting(onedrive.SETTING_AUTO_SYNC_ENABLED, "0") == "1"


def _interval_seconds() -> int:
    raw = models.get_setting(onedrive.SETTING_SYNC_INTERVAL_SECONDS)
    try:
        return max(int(raw), 30) if raw else onedrive.DEFAULT_SYNC_INTERVAL_SECONDS
    except (TypeError, ValueError):
        return onedrive.DEFAULT_SYNC_INTERVAL_SECONDS


def _due() -> bool:
    last = models.get_setting(onedrive.SETTING_LAST_SYNC_AT)
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return datetime.now() - last_dt >= timedelta(seconds=_interval_seconds())


def _maybe_restore_from_github() -> None:
    """A fresh/rebooted container may have lost its local settings table
    entirely (no persistent storage mount available on the host). Before
    giving up and telling the user to reconnect to Microsoft, try
    recovering the previous connection from the GitHub backup - this only
    ever fills in settings that are locally missing, never overwrites a
    connection that's already present."""
    if onedrive.is_connected():
        return
    try:
        from backend import github_backup
        github_backup.restore_settings()
    except Exception:
        pass


def maybe_auto_sync() -> Optional[dict]:
    """Runs a sync if due and returns a small result dict, or None if a
    sync wasn't attempted this call (not connected, disabled, or not due
    yet). Never raises - any failure is recorded in settings for display
    on the Import Stock page instead."""
    _maybe_restore_from_github()

    if not onedrive.is_connected() or not _auto_sync_enabled():
        return None

    share_url = models.get_setting(onedrive.SETTING_SHARE_URL)
    if not share_url:
        return None

    if not _due():
        return None

    # Mark "attempted now" up front so a slow/failed sync doesn't get
    # retried on every single page load in the meantime.
    models.set_setting(onedrive.SETTING_LAST_SYNC_AT, datetime.now().isoformat(timespec="seconds"))

    try:
        content, etag = onedrive.fetch_latest_stock_bytes(share_url)
    except onedrive.OneDriveError as e:
        models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR, str(e))
        return {"synced": False, "error": str(e)}

    previous_etag = models.get_setting(onedrive.SETTING_LAST_SYNC_ETAG)
    if etag and etag == previous_etag:
        models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR, "")
        return {"synced": False, "unchanged": True}

    result = import_stock_from_excel(io.BytesIO(content), replace_existing=True)
    if etag:
        models.set_setting(onedrive.SETTING_LAST_SYNC_ETAG, etag)
    if result.errors and not result.imported:
        models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR, "; ".join(result.errors[:3]))
    else:
        models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR, "")

    return {"synced": True, "imported": result.imported, "skipped": result.skipped}
