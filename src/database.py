"""SQLite 資料庫模組：初始化資料表、查詢與記錄已處理的影片。"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def _get_conn(db_path: str) -> sqlite3.Connection:
    """建立資料庫連線，並確保父目錄存在。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """初始化資料庫：若資料表不存在則建立。"""
    with _get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_videos (
                video_id     TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                channel_id   TEXT NOT NULL,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status       TEXT DEFAULT 'done'
            )
        """)
        conn.commit()


def is_processed(db_path: str, video_id: str) -> bool:
    """確認影片是否已處理過，避免重複下載。"""
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_videos WHERE video_id = ? AND status = 'done'",
            (video_id,)
        ).fetchone()
    return row is not None


def mark_processed(
    db_path: str,
    video_id: str,
    title: str,
    channel_id: str,
    status: str = "done",
) -> None:
    """記錄影片已處理完成，或標記失敗狀態。"""
    with _get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO processed_videos (video_id, title, channel_id, processed_at, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET status = excluded.status,
                                                processed_at = excluded.processed_at
            """,
            (video_id, title, channel_id, datetime.now(timezone.utc).isoformat(), status),
        )
        conn.commit()
