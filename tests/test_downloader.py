"""音訊下載模組單元測試：mock yt-dlp 避免實際下載。"""

import os
import pytest
from unittest.mock import patch, MagicMock
from src.downloader import download_audio, DownloadError


def test_download_audio_returns_path(tmp_path):
    """下載成功時應回傳正確的 mp3 路徑。"""
    video_id = "test_vid_123"
    output_dir = str(tmp_path)
    expected_path = os.path.join(output_dir, f"{video_id}.mp3")

    # 模擬 yt-dlp 下載成功並建立檔案
    def fake_download(ydl_instance, urls):
        open(expected_path, "w").close()  # 建立空檔案模擬下載完成

    with patch("src.downloader.yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_instance = MagicMock()
        mock_ydl_class.return_value.__enter__ = lambda s: mock_instance
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_instance.download.side_effect = lambda urls: open(expected_path, "w").close()

        result = download_audio(video_id, output_dir)

    assert result == expected_path


def test_download_audio_skips_existing_file(tmp_path):
    """若 mp3 已存在（重試情境），應直接回傳路徑，不重新下載。"""
    video_id = "existing_vid"
    output_dir = str(tmp_path)
    existing_path = os.path.join(output_dir, f"{video_id}.mp3")
    open(existing_path, "w").close()  # 預先建立檔案

    with patch("src.downloader.yt_dlp.YoutubeDL") as mock_ydl_class:
        result = download_audio(video_id, output_dir)
        mock_ydl_class.assert_not_called()  # 確認沒有重新下載

    assert result == existing_path


def test_download_audio_raises_on_failure(tmp_path):
    """yt-dlp 報錯時應拋出 DownloadError。"""
    import yt_dlp

    with patch("src.downloader.yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_instance = MagicMock()
        mock_ydl_class.return_value.__enter__ = lambda s: mock_instance
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_instance.download.side_effect = yt_dlp.utils.DownloadError("網路錯誤")

        with pytest.raises(DownloadError, match="下載失敗"):
            download_audio("bad_vid", str(tmp_path))
