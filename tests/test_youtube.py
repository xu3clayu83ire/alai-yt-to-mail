"""YouTube 模組單元測試：使用 mock 避免實際呼叫 API。"""

import pytest
from unittest.mock import MagicMock, patch
from src.youtube import get_channel_id, get_latest_shorts, VideoInfo


@pytest.fixture
def mock_youtube():
    """建立 mock YouTube API 客戶端。"""
    with patch("src.youtube.build") as mock_build:
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        yield mock_client


def test_get_channel_id_from_url_with_channel_prefix():
    """直接從 /channel/UC... URL 解析 channel_id，不需呼叫 API。"""
    result = get_channel_id("fake_key", "https://www.youtube.com/channel/UC12345")
    assert result == "UC12345"


def test_get_channel_id_from_handle(mock_youtube):
    """透過 @handle 呼叫 API 取得 channel_id。"""
    mock_youtube.channels().list().execute.return_value = {
        "items": [{"id": "UCabc123"}]
    }
    result = get_channel_id("fake_key", "https://www.youtube.com/@testchannel")
    assert result == "UCabc123"


def test_get_channel_id_not_found_raises(mock_youtube):
    """找不到頻道時應拋出 ValueError。"""
    mock_youtube.channels().list().execute.return_value = {"items": []}
    with pytest.raises(ValueError, match="找不到頻道"):
        get_channel_id("fake_key", "https://www.youtube.com/@nonexistent")


def test_get_latest_shorts_returns_video_list(mock_youtube):
    """正常回傳時應轉換為 VideoInfo 清單。"""
    mock_youtube.search().list().execute.return_value = {
        "items": [
            {
                "id": {"videoId": "vid_001"},
                "snippet": {
                    "title": "測試影片一",
                    "publishedAt": "2026-05-01T00:00:00Z",
                },
            },
            {
                "id": {"videoId": "vid_002"},
                "snippet": {
                    "title": "測試影片二",
                    "publishedAt": "2026-05-01T01:00:00Z",
                },
            },
        ]
    }
    results = get_latest_shorts("fake_key", "UC12345")
    assert len(results) == 2
    assert isinstance(results[0], VideoInfo)
    assert results[0].video_id == "vid_001"
    assert results[0].title == "測試影片一"


def test_get_latest_shorts_empty_channel(mock_youtube):
    """頻道今天沒有新影片時，回傳空清單（不報錯）。"""
    mock_youtube.search().list().execute.return_value = {"items": []}
    results = get_latest_shorts("fake_key", "UC12345")
    assert results == []
