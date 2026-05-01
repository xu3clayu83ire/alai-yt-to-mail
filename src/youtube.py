"""YouTube Data API v3 模組：取得頻道 Shorts 影片清單。"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore


@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel_id: str
    published_at: str
    duration_seconds: int


def get_channel_id(api_key: str, channel_url: str) -> str:
    """從頻道 URL 解析 channel_id。

    支援格式：
    - https://www.youtube.com/@handle
    - https://www.youtube.com/channel/UCxxxx
    """
    youtube = build("youtube", "v3", developerKey=api_key)

    # 處理 /channel/UC... 格式
    if "/channel/" in channel_url:
        return channel_url.split("/channel/")[-1].split("/")[0]

    # 處理 @handle 格式
    handle = channel_url.split("@")[-1].split("/")[0]
    try:
        response = youtube.channels().list(
            part="id",
            forHandle=handle,
        ).execute()
    except HttpError as e:
        raise ValueError(f"無法透過 YouTube API 解析頻道 '{handle}'：{e}") from e

    items = response.get("items", [])
    if not items:
        raise ValueError(f"找不到頻道 handle：@{handle}")
    return items[0]["id"]


def get_latest_shorts(
    api_key: str,
    channel_id: str,
    max_results: int = 10,
    days_back: int = 1,
) -> list[VideoInfo]:
    """取得頻道最新 Shorts 影片清單（past N days）。

    使用 publishedAfter 限制查詢範圍，避免拉取大量歷史影片。
    """
    youtube = build("youtube", "v3", developerKey=api_key)

    published_after = (
        datetime.now(timezone.utc) - timedelta(days=days_back)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        search_response = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            type="video",
            videoDuration="short",   # Shorts 通常 < 4 分鐘
            publishedAfter=published_after,
            maxResults=max_results,
            order="date",
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"YouTube API 查詢失敗：{e}") from e

    videos: list[VideoInfo] = []
    for item in search_response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append(VideoInfo(
            video_id=video_id,
            title=snippet["title"],
            channel_id=channel_id,
            published_at=snippet["publishedAt"],
            duration_seconds=0,   # search API 不提供時長，可後續用 videos.list 補齊
        ))

    return videos
