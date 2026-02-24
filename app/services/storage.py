from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

LOGGER = logging.getLogger("tiktok_manager.storage")

VIDEO_STATUSES = {"draft", "ready", "uploading", "posted", "failed"}
UPLOAD_STATUSES = {"ready", "uploading", "posted", "failed"}
MEDIA_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class AppStorage:
    """SQLite-backed persistence for videos, TikTok auth, and upload queue."""

    def __init__(self, app_root: Path):
        self.app_root = Path(app_root).resolve()
        self.project_root = self.app_root.parent
        self.database_dir = self.app_root / "database"
        self.media_dir = self.app_root / "media"
        self.videos_dir = self.media_dir / "videos"
        self.backgrounds_dir = self.media_dir / "backgrounds"
        self.exports_dir = self.media_dir / "exports"
        self.db_path = self.database_dir / "app.db"

        self._ensure_directories()
        self._bootstrap_backgrounds()
        self._initialize_db()

    def _ensure_directories(self) -> None:
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.backgrounds_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def _bootstrap_backgrounds(self) -> None:
        if any(self.backgrounds_dir.iterdir()):
            return

        legacy_dir = self.project_root / "backgrounds"
        if not legacy_dir.exists():
            return

        copied = 0
        for item in legacy_dir.iterdir():
            if not item.is_file() or item.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            target = self.backgrounds_dir / item.name
            if target.exists():
                continue
            target.write_bytes(item.read_bytes())
            copied += 1

        if copied:
            LOGGER.info("Bootstrapped %s background assets", copied)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    source_path TEXT,
                    export_path TEXT,
                    caption TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (status IN ('draft','ready','uploading','posted','failed'))
                );

                CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_videos_source_path ON videos(source_path);
                CREATE INDEX IF NOT EXISTS idx_videos_export_path ON videos(export_path);

                CREATE TABLE IF NOT EXISTS tiktok_auth (
                    id INTEGER PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    open_id TEXT,
                    scope TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt TEXT,
                    error_message TEXT,
                    publish_id TEXT,
                    created_at TEXT NOT NULL,
                    CHECK (status IN ('ready','uploading','posted','failed')),
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
                CREATE INDEX IF NOT EXISTS idx_uploads_video_id ON uploads(video_id);
                """
            )
            conn.commit()

    def _validate_video_status(self, status: str) -> None:
        if status not in VIDEO_STATUSES:
            raise ValueError(f"Invalid video status: {status}")

    def _validate_upload_status(self, status: str) -> None:
        if status not in UPLOAD_STATUSES:
            raise ValueError(f"Invalid upload status: {status}")

    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    def create_or_update_video(
        self,
        *,
        filename: str,
        source_path: Optional[str] = None,
        export_path: Optional[str] = None,
        caption: Optional[str] = None,
        status: str = "draft",
    ) -> int:
        self._validate_video_status(status)
        now = utc_now_iso()

        with self._connect() as conn:
            existing = None
            if export_path:
                existing = conn.execute(
                    "SELECT id FROM videos WHERE export_path = ? ORDER BY id DESC LIMIT 1",
                    (export_path,),
                ).fetchone()
            if existing is None and source_path:
                existing = conn.execute(
                    "SELECT id FROM videos WHERE source_path = ? ORDER BY id DESC LIMIT 1",
                    (source_path,),
                ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE videos
                    SET filename = ?,
                        source_path = COALESCE(?, source_path),
                        export_path = COALESCE(?, export_path),
                        caption = COALESCE(?, caption),
                        status = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (filename, source_path, export_path, caption, status, now, int(existing["id"])),
                )
                conn.commit()
                return int(existing["id"])

            cursor = conn.execute(
                """
                INSERT INTO videos (filename, source_path, export_path, caption, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (filename, source_path, export_path, caption, status, now, now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_video_by_id(self, video_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        return self._row_to_dict(row)

    def get_video_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM videos
                WHERE source_path = ? OR export_path = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (path, path),
            ).fetchone()
        return self._row_to_dict(row)

    def list_videos(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM videos ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def update_video(
        self,
        video_id: int,
        *,
        caption: Optional[str] = None,
        status: Optional[str] = None,
        export_path: Optional[str] = None,
        source_path: Optional[str] = None,
    ) -> None:
        updates: List[str] = []
        values: List[Any] = []

        if caption is not None:
            updates.append("caption = ?")
            values.append(caption)
        if status is not None:
            self._validate_video_status(status)
            updates.append("status = ?")
            values.append(status)
        if export_path is not None:
            updates.append("export_path = ?")
            values.append(export_path)
        if source_path is not None:
            updates.append("source_path = ?")
            values.append(source_path)

        if not updates:
            return

        updates.append("updated_at = ?")
        values.append(utc_now_iso())
        values.append(video_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE videos SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            conn.commit()

    def delete_video(self, video_id: int) -> Optional[Dict[str, Any]]:
        row = self.get_video_by_id(video_id)
        if row is None:
            return None
        with self._connect() as conn:
            conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            conn.commit()
        return row

    def save_auth(
        self,
        *,
        access_token: str,
        refresh_token: str,
        expires_at: str,
        open_id: Optional[str],
        scope: Optional[str],
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tiktok_auth (id, access_token, refresh_token, expires_at, open_id, scope, created_at, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    expires_at=excluded.expires_at,
                    open_id=excluded.open_id,
                    scope=excluded.scope,
                    updated_at=excluded.updated_at
                """,
                (access_token, refresh_token, expires_at, open_id, scope, now, now),
            )
            conn.commit()

    def get_auth(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tiktok_auth WHERE id = 1").fetchone()
        return self._row_to_dict(row)

    def clear_auth(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tiktok_auth WHERE id = 1")
            conn.commit()

    def enqueue_upload(self, video_id: int) -> int:
        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, status FROM uploads WHERE video_id = ? ORDER BY id DESC LIMIT 1",
                (video_id,),
            ).fetchone()
            if existing and existing["status"] in {"ready", "uploading", "failed"}:
                upload_id = int(existing["id"])
                conn.execute(
                    """
                    UPDATE uploads
                    SET status = 'ready', retry_count = 0, last_attempt = NULL, error_message = NULL
                    WHERE id = ?
                    """,
                    (upload_id,),
                )
                conn.commit()
                return upload_id

            cursor = conn.execute(
                """
                INSERT INTO uploads (video_id, status, retry_count, last_attempt, error_message, publish_id, created_at)
                VALUES (?, 'ready', 0, NULL, NULL, NULL, ?)
                """,
                (video_id, now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_upload_by_video_id(self, video_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM uploads WHERE video_id = ? ORDER BY id DESC LIMIT 1",
                (video_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def update_upload(
        self,
        upload_id: int,
        *,
        status: Optional[str] = None,
        retry_count: Optional[int] = None,
        last_attempt: Optional[str] = None,
        error_message: Optional[str] = None,
        publish_id: Optional[str] = None,
    ) -> None:
        updates: List[str] = []
        values: List[Any] = []

        if status is not None:
            self._validate_upload_status(status)
            updates.append("status = ?")
            values.append(status)
        if retry_count is not None:
            updates.append("retry_count = ?")
            values.append(retry_count)
        if last_attempt is not None:
            updates.append("last_attempt = ?")
            values.append(last_attempt)
        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)
        if publish_id is not None:
            updates.append("publish_id = ?")
            values.append(publish_id)

        if not updates:
            return

        values.append(upload_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE uploads SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            conn.commit()

    def reset_upload(self, video_id: int) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM uploads WHERE video_id = ? ORDER BY id DESC LIMIT 1",
                (video_id,),
            ).fetchone()
            if not row:
                return None
            upload_id = int(row["id"])
            conn.execute(
                """
                UPDATE uploads
                SET status = 'ready', retry_count = 0, last_attempt = NULL, error_message = NULL
                WHERE id = ?
                """,
                (upload_id,),
            )
            conn.commit()
            return upload_id

    def reset_inflight_uploads(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE uploads SET status = 'ready' WHERE status = 'uploading'"
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def fetch_upload_candidates(self, *, max_retries: int, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM uploads
                WHERE status IN ('ready', 'failed')
                  AND retry_count < ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (max_retries, limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def list_uploads(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT uploads.*, videos.filename, videos.export_path, videos.source_path, videos.status AS video_status
                FROM uploads
                JOIN videos ON videos.id = uploads.video_id
                ORDER BY uploads.id DESC
                """
            ).fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def get_video_queue_view(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    videos.id,
                    videos.filename,
                    videos.source_path,
                    videos.export_path,
                    videos.caption,
                    videos.status,
                    videos.created_at,
                    uploads.id AS upload_id,
                    uploads.status AS upload_status,
                    uploads.retry_count,
                    uploads.last_attempt,
                    uploads.error_message
                FROM videos
                LEFT JOIN uploads ON uploads.video_id = videos.id
                    AND uploads.id = (
                        SELECT u2.id
                        FROM uploads u2
                        WHERE u2.video_id = videos.id
                        ORDER BY u2.id DESC
                        LIMIT 1
                    )
                ORDER BY videos.created_at DESC
                """
            ).fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]


def auth_seconds_remaining(auth_row: Optional[Dict[str, Any]]) -> int:
    if not auth_row:
        return 0
    try:
        expires_at = parse_iso(str(auth_row["expires_at"]))
    except Exception:
        return 0
    delta = expires_at - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds()))
