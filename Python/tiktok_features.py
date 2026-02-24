#!/usr/bin/env python3
"""Feature CLI backed by production SQLite/media services."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import configure_logging
from app.services.storage import AppStorage, auth_seconds_remaining

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_accounts_table(storage: AppStorage) -> None:
    conn = sqlite3.connect(str(storage.db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT,
                niche TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                followers INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def list_accounts(storage: AppStorage, niche: str | None = None) -> list[dict]:
    ensure_accounts_table(storage)
    conn = sqlite3.connect(str(storage.db_path))
    conn.row_factory = sqlite3.Row
    try:
        if niche:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE niche = ? ORDER BY username ASC", (niche,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM accounts ORDER BY username ASC").fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]
    finally:
        conn.close()


def add_account(storage: AppStorage, username: str, niche: str, display_name: str) -> bool:
    ensure_accounts_table(storage)
    conn = sqlite3.connect(str(storage.db_path))
    try:
        conn.execute(
            """
            INSERT INTO accounts (username, display_name, niche, status, followers, created_at)
            VALUES (?, ?, ?, 'active', 0, ?)
            ON CONFLICT(username) DO UPDATE SET
                display_name = excluded.display_name,
                niche = excluded.niche,
                status = 'active'
            """,
            (username, display_name, niche, now_iso()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def analytics(storage: AppStorage, username: str | None = None) -> dict:
    queue_rows = storage.get_video_queue_view()
    posted = [row for row in queue_rows if (row.get("upload_status") or "") == "posted"]
    failed = [row for row in queue_rows if (row.get("upload_status") or "") == "failed"]

    account_count = len(list_accounts(storage, niche=None))

    # This app does not receive view/like webhooks yet, so totals are queue-based operational metrics.
    return {
        "total_views": 0,
        "total_likes": 0,
        "total_posts": len(posted),
        "active_accounts": account_count,
        "follower_growth": 0,
        "failed_uploads": len(failed),
    }


def command_status(storage: AppStorage) -> int:
    auth = storage.get_auth()
    connected = bool(auth and auth_seconds_remaining(auth) > 0)
    backgrounds = [
        p for p in storage.backgrounds_dir.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png"}
    ]
    queue_rows = storage.get_video_queue_view()

    print("TIKTOK FEATURES STATUS")
    print(f"oauth_connected: {str(connected).lower()}")
    print(f"oauth_expires_at: {auth.get('expires_at') if auth else ''}")
    print(f"backgrounds: {len(backgrounds)}")
    print(f"videos: {len(queue_rows)}")
    print(f"queued_uploads: {len([r for r in queue_rows if (r.get('upload_status') or '') in ('ready','uploading')])}")
    print(f"failed_uploads: {len([r for r in queue_rows if (r.get('upload_status') or '') == 'failed'])}")
    return 0


def command_backgrounds(storage: AppStorage) -> int:
    backgrounds = sorted(
        [
            p
            for p in storage.backgrounds_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png"}
        ],
        key=lambda p: p.name.lower(),
    )
    print(f"\nAvailable Backgrounds: {len(backgrounds)}")
    for bg in backgrounds:
        print(f"- {bg.name}")
    return 0


def command_download_backgrounds(storage: AppStorage) -> int:
    legacy_dir = PROJECT_ROOT / "backgrounds"
    if not legacy_dir.exists():
        print("ERROR: No legacy backgrounds directory found to import from.")
        return 1

    copied = 0
    for item in legacy_dir.iterdir():
        if not item.is_file() or item.suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png"}:
            continue
        target = storage.backgrounds_dir / item.name
        if target.exists():
            continue
        target.write_bytes(item.read_bytes())
        copied += 1

    print(f"Downloaded {copied} backgrounds")
    return 0


def command_add_account(storage: AppStorage, args: argparse.Namespace) -> int:
    if not args.username or not args.niche:
        print("ERROR: --username and --niche required")
        return 1

    ok = add_account(storage, username=args.username, niche=args.niche, display_name=args.name or args.username)
    if ok:
        print(f"Added account: @{args.username}")
        return 0
    print("ERROR: Failed to add account")
    return 1


def command_list_accounts(storage: AppStorage, args: argparse.Namespace) -> int:
    rows = list_accounts(storage, niche=args.niche)
    print(f"\nAccounts: {len(rows)}")
    for account in rows:
        print(
            f"@{account['username']} - {account.get('niche') or ''} - {account.get('status') or 'active'} - {int(account.get('followers') or 0)} followers"
        )
    return 0


def command_analytics(storage: AppStorage, args: argparse.Namespace) -> int:
    payload = analytics(storage, username=args.username)
    print("\nAnalytics:")
    print(f"total_views: {payload.get('total_views', 0)}")
    print(f"total_likes: {payload.get('total_likes', 0)}")
    print(f"total_posts: {payload.get('total_posts', 0)}")
    print(f"active_accounts: {payload.get('active_accounts', 0)}")
    print(f"follower_growth: {payload.get('follower_growth', 0)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok Upload Manager feature CLI")
    parser.add_argument(
        "command",
        choices=["status", "backgrounds", "download-backgrounds", "add-account", "list-accounts", "analytics"],
    )
    parser.add_argument("--theme", default="scary")
    parser.add_argument("--username")
    parser.add_argument("--niche")
    parser.add_argument("--name")
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()
    storage = AppStorage(PROJECT_ROOT / "app")

    if args.command == "status":
        return command_status(storage)
    if args.command == "backgrounds":
        return command_backgrounds(storage)
    if args.command == "download-backgrounds":
        return command_download_backgrounds(storage)
    if args.command == "add-account":
        return command_add_account(storage, args)
    if args.command == "list-accounts":
        return command_list_accounts(storage, args)
    if args.command == "analytics":
        return command_analytics(storage, args)

    print("ERROR: Unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
