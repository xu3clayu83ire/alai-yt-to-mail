"""
管理員路由模組。

所有端點均需持有 admin JWT（透過 get_current_admin 依賴函式驗證）。
管理員可跨用戶查詢所有訂閱資料，以及強制刪除任意訂閱，
不受擁有者（user_id）限制，適用於客服與後台維運場景。

設計決策：
- 使用 scan_table 全表掃描而非 GSI Query，因管理員需要所有用戶資料。
- email 篩選在 Python 端完成，避免在 scan 加入 FilterExpression
  而需要額外的 ExpressionAttributeValues（小規模資料表可接受）。
- 刪除前先 GetItem 確認存在，確保 404 語意正確。
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_current_admin
from models.subscription import AdminSubscriptionResponse
from services.dynamo_service import delete_item, get_item, scan_table

router = APIRouter()

_SUBSCRIPTIONS_TABLE: str = os.environ.get("SUBSCRIPTIONS_TABLE", "yt-to-mail-subscriptions")


@router.get("/subscriptions", response_model=list[AdminSubscriptionResponse])
async def admin_list_subscriptions(
    email: Optional[str] = None,
    _admin: dict = Depends(get_current_admin),
) -> list[AdminSubscriptionResponse]:
    """
    管理員查詢全部訂閱端點。

    以 scan_table 取得所有訂閱後，若傳入 email 查詢參數，
    則在 Python 端篩選 item["user_id"] == email，
    讓管理員可快速定位特定用戶的所有訂閱紀錄。
    未傳入 email 時回傳完整訂閱清單（後台管理用途）。
    回傳 AdminSubscriptionResponse 含 user_id 欄位，
    讓管理員能辨識每筆訂閱的擁有者。
    """
    items = scan_table(_SUBSCRIPTIONS_TABLE)

    # email 篩選：比對 user_id 欄位（公開訂閱以 email 作為 user_id）
    if email:
        items = [item for item in items if item.get("user_id") == email]

    result: list[AdminSubscriptionResponse] = []
    for item in items:
        result.append(
            AdminSubscriptionResponse(
                id=str(item.get("id", "")),
                user_id=str(item.get("user_id", "")),
                channel_url=str(item.get("channel_url", "")),
                channel_id=str(item.get("channel_id", "")),
                channel_name=str(item.get("channel_name", "")),
                recipient_email=str(item.get("recipient_email", "")),
                audio_speed=float(item.get("audio_speed", 1.0)),
                send_time=str(item.get("send_time", "00:00")),
                is_active=bool(item.get("is_active", True)),
                auto_cancel_days=int(item.get("auto_cancel_days", 3)),
                no_new_video_days=int(item.get("no_new_video_days", 0)),
                created_at=str(item.get("created_at", "")),
            )
        )

    return result


@router.delete("/subscriptions/{subscription_id}")
async def admin_delete_subscription(
    subscription_id: str,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    """
    管理員強制刪除訂閱端點。

    不驗證擁有者（user_id），管理員可刪除任意用戶的訂閱，
    適用於處理用戶申訴、資料異常清理等維運場景。
    刪除前先 GetItem 確認項目存在，確保 404 語意正確，
    避免對不存在的資源回傳 200 造成前端誤判。
    """
    existing = get_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="訂閱不存在",
        )

    delete_item(
        table_name=_SUBSCRIPTIONS_TABLE,
        key={"id": subscription_id},
    )

    return {"message": "deleted"}
