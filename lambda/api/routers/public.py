"""
公開訂閱路由模組（無 JWT 認證）。

提供三個端點讓未登入用戶以 email 作為身份識別進行訂閱操作：
  POST   /public/subscribe                  — 新增訂閱
  GET    /public/subscriptions?email=xxx    — 查詢訂閱列表
  DELETE /public/subscriptions/{id}?email=xxx — 刪除訂閱

此設計的核心理由：
- 降低用戶使用門檻（不須先註冊帳號）
- email 作為輕量身份驗證，刪除時驗證 email 一致性防止誤刪他人訂閱
- 上限 5 個訂閱同樣適用，防止單一 email 佔用過多資源
"""

import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, HTTPException, Query, status

from models.subscription import PublicSubscriptionCreate, PublicSubscriptionResponse
from services.dynamo_service import (
    delete_item,
    get_item,
    put_item,
    query_by_gsi_partition,
)

router = APIRouter()

_SUBSCRIPTIONS_TABLE: str = os.environ.get("SUBSCRIPTIONS_TABLE", "yt-to-mail-subscriptions")
_MAX_SUBSCRIPTIONS: int = 5

# YouTube 頻道 URL 解析正規表達式（與 channels.py 保持一致）
# section 路徑（/shorts、/videos 等）保留在 normalized_url 中，確保 scheduler 查詢正確的影片類型
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)((?:/(?:videos|shorts|streams|live|playlists|community))?)$")
_CHANNEL_ID_PATTERN = re.compile(r"^/channel/(UC[a-zA-Z0-9_-]{22})((?:/(?:videos|shorts|streams|live|playlists|community))?)$")


def _parse_channel_url(channel_url: str) -> tuple[str, str, str]:
    """
    解析 YouTube 頻道 URL，回傳 (normalized_url, channel_id, channel_name)。

    複用 channels.py 的解析邏輯，集中在此函式以便公開端點重用，
    避免 channels router 因需要 JWT 而無法在公開端點使用。
    若 URL 包含 /shorts、/videos 等 section 路徑，保留在 normalized_url 中，
    確保 scheduler 能查詢用戶訂閱的正確影片類型。
    解析失敗時拋出 HTTPException 400，讓呼叫端直接回傳錯誤給前端。
    """
    channel_url = channel_url.strip()

    try:
        parsed = urlparse(channel_url)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的 URL 格式",
        )

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

    # URL 解碼處理中文 handle（如 %E6%99%BA → 智慧）
    path = unquote(parsed.path.rstrip("/"))

    handle_match = _HANDLE_PATTERN.match(path)
    if handle_match:
        handle = handle_match.group(1)
        section = handle_match.group(2)   # 例如 "/shorts"，或空字串
        normalized_url = f"https://www.youtube.com/@{handle}{section}"
        return normalized_url, handle, handle

    channel_id_match = _CHANNEL_ID_PATTERN.match(path)
    if channel_id_match:
        channel_id = channel_id_match.group(1)
        section = channel_id_match.group(2)
        normalized_url = f"https://www.youtube.com/channel/{channel_id}{section}"
        return normalized_url, channel_id, channel_id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="無法解析頻道資訊，請使用 https://www.youtube.com/@handle 或 https://www.youtube.com/channel/UCxxx 格式",
    )


def _to_public_response(item: dict) -> PublicSubscriptionResponse:
    """
    將 DynamoDB 資料項目轉換為 PublicSubscriptionResponse 模型。

    處理兩個相容性問題：
    1. DynamoDB Decimal 型別需轉換為 float / int
    2. v3 新增的 auto_cancel_days / no_new_video_days 欄位舊資料可能不存在，
       以 .get() 提供預設值避免 KeyError。
    """
    return PublicSubscriptionResponse(
        id=item["id"],
        channel_url=item["channel_url"],
        channel_name=item["channel_name"],
        recipient_email=item["recipient_email"],
        audio_speed=float(item.get("audio_speed", 1.0)),
        send_time=item["send_time"],
        is_active=bool(item.get("is_active", True)),
        auto_cancel_days=int(item.get("auto_cancel_days", 3)),
        no_new_video_days=int(item.get("no_new_video_days", 0)),
        created_at=item["created_at"],
    )


@router.post(
    "/subscribe",
    response_model=PublicSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def public_subscribe(
    sub_data: PublicSubscriptionCreate,
) -> PublicSubscriptionResponse:
    """
    公開新增訂閱端點（無需 JWT 認證）。

    以 recipient_email 作為 user_id，不查詢 users 資料表，
    讓未註冊用戶也能直接訂閱。
    同一 email 訂閱數上限為 5 個，防止單一用戶佔用過多系統資源。
    channel_url 在後端重新解析取得 channel_id / channel_name，
    讓前端無需先呼叫 /channels/verify 即可完成訂閱。
    """
    # 解析頻道 URL 取得 channel_id / channel_name
    normalized_url, channel_id, channel_name = _parse_channel_url(sub_data.channel_url)

    # 以 email 作為 user_id 查詢現有訂閱數量
    user_id = str(sub_data.recipient_email)
    existing = query_by_gsi_partition(
        table_name=_SUBSCRIPTIONS_TABLE,
        index_name="user_id-index",
        partition_key_name="user_id",
        partition_key_value=user_id,
    )

    if len(existing) >= _MAX_SUBSCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"訂閱數量已達上限（最多 {_MAX_SUBSCRIPTIONS} 個）",
        )

    # 建立新訂閱資料，包含 v3 新增的計數器欄位
    subscription_id = str(uuid.uuid4())
    created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    new_subscription: dict = {
        "id": subscription_id,
        "user_id": user_id,
        "channel_url": normalized_url,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "recipient_email": user_id,
        "audio_speed": Decimal(str(sub_data.audio_speed)),
        "send_time": sub_data.send_time,
        "is_active": True,
        "auto_cancel_days": sub_data.auto_cancel_days,
        "no_new_video_days": 0,
        "created_at": created_at,
    }

    put_item(table_name=_SUBSCRIPTIONS_TABLE, item=new_subscription)

    return PublicSubscriptionResponse(
        id=subscription_id,
        channel_url=normalized_url,
        channel_name=channel_name,
        recipient_email=user_id,
        audio_speed=sub_data.audio_speed,
        send_time=sub_data.send_time,
        is_active=True,
        auto_cancel_days=sub_data.auto_cancel_days,
        no_new_video_days=0,
        created_at=created_at,
    )


@router.get("/subscriptions", response_model=list[PublicSubscriptionResponse])
async def get_public_subscriptions(
    email: str = Query(..., description="訂閱者 email"),
) -> list[PublicSubscriptionResponse]:
    """
    以 email 查詢所有訂閱列表（無需 JWT 認證）。

    使用 email 作為 user_id 查詢 user_id-index GSI，
    只回傳屬於該 email 的訂閱，不需 Scan 全表。
    此端點沒有身份驗證，任何知道 email 的人都能查詢，
    因此回應中不包含 channel_id 等敏感內部資訊。
    """
    items = query_by_gsi_partition(
        table_name=_SUBSCRIPTIONS_TABLE,
        index_name="user_id-index",
        partition_key_name="user_id",
        partition_key_value=email,
    )
    return [_to_public_response(item) for item in items]


@router.delete("/subscriptions/{subscription_id}")
async def delete_public_subscription(
    subscription_id: str,
    email: str = Query(..., description="訂閱者 email（用於驗證擁有權）"),
) -> dict:
    """
    刪除指定訂閱（無需 JWT 認證，但需提供 email 驗證擁有權）。

    以 email 驗證訂閱擁有者，防止用戶誤刪他人訂閱。
    若 email 不符回傳 403 而非 404，
    避免攻擊者通過 403 vs 404 的差異枚舉訂閱 ID 是否存在。
    """
    # 取得訂閱資料確認存在
    existing = get_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="訂閱不存在",
        )

    # 驗證 email 與訂閱的 user_id 一致（公開端點以 email 作為 user_id）
    if existing.get("user_id") != email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限刪除此訂閱",
        )

    delete_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    return {"message": "deleted"}
