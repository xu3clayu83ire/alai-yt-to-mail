"""YouTube Data API v3 模組：取得頻道 Shorts 影片清單。"""

import re
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

    if "/channel/" in channel_url:
        return channel_url.split("/channel/")[-1].split("/")[0]

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


def _parse_duration_seconds(iso_duration: str) -> int:
    """將 ISO 8601 時長格式轉換為秒數。

    例如：PT45S → 45、PT1M30S → 90、PT2M → 120
    """
    match = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        iso_duration,
    )
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _fetch_durations(youtube, video_ids: list[str]) -> dict[str, int]:
    """批次查詢影片時長，回傳 {video_id: duration_seconds}。"""
    if not video_ids:
        return {}
    try:
        response = youtube.videos().list(
            part="contentDetails",
            id=",".join(video_ids),
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"YouTube API 查詢影片時長失敗：{e}") from e

    return {
        item["id"]: _parse_duration_seconds(item["contentDetails"]["duration"])
        for item in response.get("items", [])
    }


def get_latest_shorts(
    api_key: str,
    channel_id: str,
    max_results: int = 10,
    days_back: int = 7,
    max_duration_seconds: int = 60,
) -> list[VideoInfo]:
    """取得頻道最新 Shorts 影片清單（past N days，時長 ≤ max_duration_seconds）。

    三層過濾確保只抓到真正的 Shorts：
    1. YouTube API videoDuration="short"（< 4 分鐘）
    2. videos.list 取得實際時長
    3. 過濾時長 ≤ max_duration_seconds（預設 60 秒）
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
            videoDuration="short",
            publishedAfter=published_after,
            maxResults=max_results,
            order="date",
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"YouTube API 查詢失敗：{e}") from e

    items = search_response.get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items]
    durations = _fetch_durations(youtube, video_ids)

    videos: list[VideoInfo] = []
    for item in items:
        video_id = item["id"]["videoId"]
        duration = durations.get(video_id, 0)
        if duration > max_duration_seconds:
            continue
        snippet = item["snippet"]
        videos.append(VideoInfo(
            video_id=video_id,
            title=snippet["title"],
            channel_id=channel_id,
            published_at=snippet["publishedAt"],
            duration_seconds=duration,
        ))

    return videos
