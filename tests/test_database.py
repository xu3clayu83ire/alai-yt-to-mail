"""資料庫模組單元測試：驗證初始化、去重複查詢與狀態記錄功能。"""

import pytest
import tempfile
import os
from src.database import init_db, is_processed, mark_processed


@pytest.fixture
def db_path(tmp_path):
    """每個測試使用獨立的臨時資料庫。"""
    return str(tmp_path / "test.db")


def test_init_db_creates_table(db_path):
    """初始化後資料表應存在。"""
    init_db(db_path)
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    assert any("processed_videos" in str(t) for t in tables)


def test_is_processed_returns_false_for_new_video(db_path):
    """未處理的影片應回傳 False。"""
    init_db(db_path)
    assert is_processed(db_path, "test_video_001") is False


def test_mark_and_check_processed(db_path):
    """標記完成後，查詢應回傳 True。"""
    init_db(db_path)
    mark_processed(db_path, "vid_123", "測試影片", "ch_abc", status="done")
    assert is_processed(db_path, "vid_123") is True


def test_failed_video_not_counted_as_processed(db_path):
    """標記失敗的影片不視為已處理，允許重新嘗試。"""
    init_db(db_path)
    mark_processed(db_path, "vid_456", "失敗影片", "ch_abc", status="failed")
    assert is_processed(db_path, "vid_456") is False


def test_mark_processed_idempotent(db_path):
    """重複標記同一影片不應報錯，狀態更新為最新值。"""
    init_db(db_path)
    mark_processed(db_path, "vid_789", "影片A", "ch_abc", status="failed")
    mark_processed(db_path, "vid_789", "影片A", "ch_abc", status="done")
    assert is_processed(db_path, "vid_789") is True
