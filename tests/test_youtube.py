"""YouTube 模組測試：驗證時長解析與 Shorts 過濾邏輯。"""

import pytest
from unittest.mock import MagicMock, patch
from src.youtube import _parse_duration_seconds, get_latest_shorts, VideoInfo


# --- _parse_duration_seconds ---

@pytest.mark.parametrize("iso, expected", [
    ("PT45S", 45),
    ("PT1M", 60),
    ("PT1M30S", 90),
    ("PT2M", 120),
    ("PT1H", 3600),
    ("PT1H2M3S", 3723),
    ("PT0S", 0),
    ("INVALID", 0),
])
def test_parse_duration_seconds(iso, expected):
    """各種 ISO 8601 格式應正確轉換為秒數。"""
    assert _parse_duration_seconds(iso) == expected


# --- get_latest_shorts ---

def _make_search_item(video_id: str, title: str) -> dict:
    return {
        "id": {"videoId": video_id},
        "snippet": {
            "title": title,
            "publishedAt": "2026-04-30T10:00:00Z",
        },
    }


def _make_videos_list_response(items: list[tuple[str, str]]) -> dict:
    """items: [(video_id, iso_duration)]"""
    return {
        "items": [
            {"id": vid, "contentDetails": {"duration": dur}}
            for vid, dur in items
        ]
    }


@patch("src.youtube.build")
def test_get_latest_shorts_filters_over_60s(mock_build):
    """超過 60 秒的影片應被過濾掉，只回傳 ≤ 60 秒的影片。"""
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube

    mock_youtube.search().list().execute.return_value = {
        "items": [
            _make_search_item("vid_45s", "Short A"),
            _make_search_item("vid_90s", "Normal Video"),
            _make_search_item("vid_60s", "Short B"),
        ]
    }
    mock_youtube.videos().list().execute.return_value = _make_videos_list_response([
        ("vid_45s", "PT45S"),
        ("vid_90s", "PT1M30S"),
        ("vid_60s", "PT60S"),
    ])

    result = get_latest_shorts("fake_key", "UC_fake_channel_id")

    assert len(result) == 2
    ids = [v.video_id for v in result]
    assert "vid_45s" in ids
    assert "vid_60s" in ids
    assert "vid_90s" not in ids


@patch("src.youtube.build")
def test_get_latest_shorts_duration_populated(mock_build):
    """回傳的 VideoInfo 應包含正確的 duration_seconds。"""
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube

    mock_youtube.search().list().execute.return_value = {
        "items": [_make_search_item("vid1", "My Short")]
    }
    mock_youtube.videos().list().execute.return_value = _make_videos_list_response([
        ("vid1", "PT30S"),
    ])

    result = get_latest_shorts("fake_key", "UC_fake")

    assert len(result) == 1
    assert result[0].duration_seconds == 30


@patch("src.youtube.build")
def test_get_latest_shorts_empty_channel(mock_build):
    """頻道近期無影片時應回傳空清單。"""
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube
    mock_youtube.search().list().execute.return_value = {"items": []}

    result = get_latest_shorts("fake_key", "UC_fake")

    assert result == []
