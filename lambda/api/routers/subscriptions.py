"""
訂閱管理路由模組。

提供訂閱的 CRUD 操作（GET / POST / PUT / DELETE）。
所有端點都需要 JWT 認證，確保用戶只能操作自己的訂閱。

POST 新增時檢查同一 user_id 的訂閱數量上限（最多 5 個），
超過上限回傳 400 Bad Request。

PUT / DELETE 時先確認訂閱存在且屬於當前用戶，
不屬於當前用戶時回傳 403 Forbidden（而非 404），
避免洩漏其他用戶的訂閱 ID。
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_current_user
from models.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate
from services.dynamo_service import (
    delete_item,
    get_item,
    put_item,
    query_by_gsi_partition,
    update_item,
)

router = APIRouter()

_SUBSCRIPTIONS_TABLE: str = os.environ.get("SUBSCRIPTIONS_TABLE", "yt-to-mail-subscriptions")
_MAX_SUBSCRIPTIONS: int = 5


def _to_response(item: dict) -> SubscriptionResponse:
    """
    將 DynamoDB 資料項目轉換為 SubscriptionResponse 模型。

    DynamoDB 儲存數字為 Decimal 型別，需轉換為 float 才能序列化。
    集中在此轉換，避免各個端點重複撰寫型別轉換邏輯。
    """
    return SubscriptionResponse(
        id=item["id"],
        channel_url=item["channel_url"],
        channel_id=item["channel_id"],
        channel_name=item["channel_name"],
        recipient_email=item["recipient_email"],
        audio_speed=float(item.get("audio_speed", 1.0)),
        send_time=item["send_time"],
        is_active=bool(item.get("is_active", True)),
        created_at=item["created_at"],
    )


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    current_user: dict = Depends(get_current_user),
) -> list[SubscriptionResponse]:
    """
    取得當前用戶的所有訂閱列表。

    透過 user_id-index GSI 查詢，只回傳屬於當前用戶的訂閱，
    不需要 Scan 全表，效能穩定且成本可控。
    """
    items = query_by_gsi_partition(
        table_name=_SUBSCRIPTIONS_TABLE,
        index_name="user_id-index",
        partition_key_name="user_id",
        partition_key_value=current_user["user_id"],
    )
    return [_to_response(item) for item in items]


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    sub_data: SubscriptionCreate,
    current_user: dict = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    新增訂閱。

    新增前先查詢該用戶現有訂閱數量，超過 5 個上限時回傳 400。
    此上限設計是為了控制排程器的每日執行成本，
    避免單一用戶建立過多訂閱導致系統負載過高。
    """
    # 查詢現有訂閱數量
    existing = query_by_gsi_partition(
        table_name=_SUBSCRIPTIONS_TABLE,
        index_name="user_id-index",
        partition_key_name="user_id",
        partition_key_value=current_user["user_id"],
    )

    if len(existing) >= _MAX_SUBSCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"訂閱數量已達上限（最多 {_MAX_SUBSCRIPTIONS} 個）",
        )

    # 建立新訂閱資料
    subscription_id = str(uuid.uuid4())
    created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    new_subscription = {
        "id": subscription_id,
        "user_id": current_user["user_id"],
        "channel_url": sub_data.channel_url,
        "channel_id": sub_data.channel_id,
        "channel_name": sub_data.channel_name,
        "recipient_email": str(sub_data.recipient_email),
        "audio_speed": Decimal(str(sub_data.audio_speed)),
        "send_time": sub_data.send_time,
        "is_active": True,
        "created_at": created_at,
    }

    put_item(table_name=_SUBSCRIPTIONS_TABLE, item=new_subscription)

    return SubscriptionResponse(
        id=subscription_id,
        channel_url=sub_data.channel_url,
        channel_id=sub_data.channel_id,
        channel_name=sub_data.channel_name,
        recipient_email=str(sub_data.recipient_email),
        audio_speed=sub_data.audio_speed,
        send_time=sub_data.send_time,
        is_active=True,
        created_at=created_at,
    )


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: str,
    update_data: SubscriptionUpdate,
    current_user: dict = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    修改訂閱設定。

    修改前先確認訂閱存在且屬於當前用戶，
    不屬於當前用戶時回傳 403（而非 404），
    這樣做可以防止攻擊者通過 404 vs 403 的差異枚舉訂閱 ID。
    """
    # 取得現有訂閱資料
    existing = get_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="訂閱不存在",
        )

    if existing.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限修改此訂閱",
        )

    # 只更新傳入的欄位（部分更新）
    update_fields: dict = {}
    if update_data.recipient_email is not None:
        update_fields["recipient_email"] = str(update_data.recipient_email)
    if update_data.audio_speed is not None:
        update_fields["audio_speed"] = Decimal(str(update_data.audio_speed))
    if update_data.send_time is not None:
        update_fields["send_time"] = update_data.send_time
    if update_data.is_active is not None:
        update_fields["is_active"] = update_data.is_active

    if not update_fields:
        # 沒有要更新的欄位，直接回傳現有資料
        return _to_response(existing)

    updated = update_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
        update_fields=update_fields,
    )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新訂閱失敗",
        )

    return _to_response(updated)


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    刪除訂閱。

    刪除前同樣先驗證擁有者，不屬於當前用戶時回傳 403。
    刪除成功後回傳 {"message": "deleted"} 讓前端確認操作結果。
    """
    # 確認訂閱存在且屬於當前用戶
    existing = get_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="訂閱不存在",
        )

    if existing.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限刪除此訂閱",
        )

    delete_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    return {"message": "deleted"}
