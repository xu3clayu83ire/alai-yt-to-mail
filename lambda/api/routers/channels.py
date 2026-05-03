"""
頻道驗證路由模組。

提供 POST /channels/verify 端點，讓前端在新增訂閱前
先確認 YouTube 頻道 URL 格式是否正確並取得頻道資訊。

原型階段不呼叫 YouTube Data API，僅做 URL 格式解析與正規化。
支援兩種 YouTube 頻道 URL 格式：
- /@handle 格式：https://www.youtube.com/@channelname
- /channel/UCxxx 格式：https://www.youtube.com/channel/UCxxxxxxxxxx

此設計的好處：
- 前端可以即時驗證用戶輸入的 URL 是否合法
- 不需要 YouTube API 金鑰即可在原型階段運作
- Phase 2 可以直接替換為真實 YouTube API 查詢
"""

import re
from urllib.parse import urlparse, unquote

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()

# YouTube 頻道 URL 的正規表達式
# handle 支援 Unicode（中文等）與可選的尾段路徑（/shorts、/videos 等）
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(?:/.*)?$")
_CHANNEL_ID_PATTERN = re.compile(r"^/channel/(UC[a-zA-Z0-9_-]{22})(?:/.*)?$")


class ChannelVerifyRequest(BaseModel):
    """頻道驗證請求模型。"""
    channel_url: str


class ChannelVerifyResponse(BaseModel):
    """
    頻道驗證回應模型。

    channel_id 在 /@handle 格式下暫填 handle 值（原型階段），
    Phase 2 接入 YouTube Data API 後才會回傳真實的 UCxxx ID。
    """
    channel_url: str
    channel_id: str
    channel_name: str


@router.post("/verify", response_model=ChannelVerifyResponse)
async def verify_channel(
    request: ChannelVerifyRequest,
) -> ChannelVerifyResponse:
    """
    驗證 YouTube 頻道 URL 並解析頻道資訊。

    只接受 youtube.com 網域，拒絕其他網域的 URL，
    防止 SSRF 或用戶輸入惡意 URL 的情況。
    解析成功時回傳正規化的 channel_url、channel_id 與 channel_name。
    """
    channel_url = request.channel_url.strip()

    # 驗證基本 URL 格式
    try:
        parsed = urlparse(channel_url)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的 URL 格式",
        )

    # 確認為 YouTube 網域
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL 必須使用 http 或 https 協定",
        )

    hostname = parsed.netloc.lower()
    if hostname not in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL 必須為 YouTube 頻道網址（youtube.com）",
        )

    # 解析頻道路徑（URL 解碼處理中文 handle，如 %E6%99%BA → 智慧）
    path = unquote(parsed.path.rstrip("/"))

    # 嘗試 /@handle 格式
    handle_match = _HANDLE_PATTERN.match(path)
    if handle_match:
        handle = handle_match.group(1)
        normalized_url = f"https://www.youtube.com/@{handle}"
        return ChannelVerifyResponse(
            channel_url=normalized_url,
            channel_id=handle,          # 原型階段暫以 handle 填充
            channel_name=handle,         # 原型階段暫以 handle 填充
        )

    # 嘗試 /channel/UCxxx 格式
    channel_id_match = _CHANNEL_ID_PATTERN.match(path)
    if channel_id_match:
        channel_id = channel_id_match.group(1)
        normalized_url = f"https://www.youtube.com/channel/{channel_id}"
        return ChannelVerifyResponse(
            channel_url=normalized_url,
            channel_id=channel_id,
            channel_name=channel_id,    # 原型階段暫以 channel_id 填充
        )

    # 無法解析的 YouTube URL 格式
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="無法解析頻道資訊，請使用 https://www.youtube.com/@handle 或 https://www.youtube.com/channel/UCxxx 格式",
    )
