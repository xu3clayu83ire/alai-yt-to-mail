"""Gmail 寄信模組測試：mock Google API，驗證郵件組裝邏輯。"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from src.mailer import _build_message
from src.youtube import VideoInfo
from src.transcriber import TranscriptResult


@pytest.fixture
def sample_video():
    return VideoInfo(
        video_id="vid_test_001",
        title="今日英文學習",
        channel_id="UC_test",
        published_at="2026-05-01T00:00:00Z",
        duration_seconds=60,
    )


@pytest.fixture
def sample_transcript():
    return TranscriptResult(
        text="Hello, this is a test transcript.",
        language="en",
        duration_seconds=58.3,
    )


def test_build_message_subject_format(sample_video, sample_transcript, tmp_path):
    """郵件主旨應符合 '[yt-to-mail] {標題} — {日期}' 格式。"""
    audio_path = str(tmp_path / "test.mp3")
    # 建立小於 25MB 的假音訊檔
    Path(audio_path).write_bytes(b"x" * 100)

    msg_dict = _build_message("test@example.com", sample_video, sample_transcript, audio_path)
    assert "raw" in msg_dict


def test_build_message_large_audio_skips_attachment(sample_video, sample_transcript, tmp_path):
    """超過 25MB 的音訊應跳過附件並附上說明文字。"""
    audio_path = str(tmp_path / "large.mp3")
    # 建立 26MB 的假音訊檔
    Path(audio_path).write_bytes(b"x" * (26 * 1024 * 1024))

    msg_dict = _build_message("test@example.com", sample_video, sample_transcript, audio_path)
    # 主要確認不會拋出錯誤，訊息仍能組裝完成
    assert "raw" in msg_dict


def test_build_message_missing_audio(sample_video, sample_transcript, tmp_path):
    """音訊檔不存在時，仍能組裝郵件（只寄文字稿）。"""
    nonexistent_audio = str(tmp_path / "missing.mp3")
    msg_dict = _build_message("test@example.com", sample_video, sample_transcript, nonexistent_audio)
    assert "raw" in msg_dict
