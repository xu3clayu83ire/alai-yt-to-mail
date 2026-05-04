"""
管理員頻道白名單路由模組。

提供四個端點讓管理員維護可訂閱頻道清單：
  POST   /admin/channels            — 新增頻道
  GET    /admin/channels            — 列出所有頻道
  PATCH  /admin/channels/{channel_id} — 更新頻道資訊
  DELETE /admin/channels/{channel_id} — 刪除頻道（串聯取消所有相關訂閱並寄通知信）

所有端點均需管理員 JWT（Depends get_current_admin），
一般用戶持有合法 token 也無法存取（回傳 403）。

DELETE 串聯邏輯設計理由：
- 以 channel_id-index GSI 高效查詢所有受影響訂閱，避免全表 Scan
- 在同一個同步請求中完成：查詢 → 寄信 → 刪訂閱 → 刪頻道
- Lambda timeout 30 秒，小規模訂閱數量足夠處理，不引入非同步佇列以降低複雜度
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_current_admin
from models.channel import ChannelCreate, ChannelResponse, ChannelUpdate
from services.dynamo_service import (
    delete_item,
    get_item,
    put_item,
    query_by_gsi_partition,
    scan_table,
    update_item,
)

# gmail_sender 位於 scheduler/，admin_channels 在 Lambda 中直接 import；
# 為維持模組邊界，由呼叫端（admin_channels router）負責 import 並呼叫。
# Lambda 部署時 scheduler/ 不在 sys.path，故使用動態 import 避免 ModuleNotFoundError，
# 實際通知信由 scheduler 觸發，此處 import 為準備串聯通知用。
# 注意：Lambda 環境中 gmail_sender 不存在，改採條件式 import 並靜默略過。
try:
    import sys
    import importlib.util
    _spec = importlib.util.find_spec("gmail_sender")
    if _spec is not None:
        _gmail_sender = importlib.import_module("gmail_sender")
        _send_admin_removed_email = _gmail_sender.send_admin_removed_email
    else:
        _send_admin_removed_email = None
except Exception:
    _send_admin_removed_email = None

router = APIRouter()

_CHANNELS_TABLE: str = os.environ.get("CHANNELS_TABLE", "yt-to-mail-channels")
_SUBSCRIPTIONS_TABLE: str = os.environ.get("SUBSCRIPTIONS_TABLE", "yt-to-mail-subscriptions")


def _to_channel_response(item: dict) -> ChannelResponse:
    """
    將 DynamoDB 資料項目轉換為 ChannelResponse 模型。

    集中轉換邏輯，確保所有端點回傳格式一致，
    欄位缺失時提供預設值避免 KeyError。
    """
    return ChannelResponse(
        channel_id=item["channel_id"],
        channel_name=item.get("channel_name", ""),
        channel_url=item.get("channel_url", ""),
        created_at=item.get("created_at", ""),
    )


@router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    channel_data: ChannelCreate,
    _admin: dict = Depends(get_current_admin),
) -> ChannelResponse:
    """
    新增頻道至白名單（需管理員 JWT）。

    以 GetItem 先查詢是否已存在相同 channel_id，
    存在時回傳 409 Conflict 而非覆蓋，
    防止管理員誤操作覆蓋已有的頻道資料。
    """
    existing = get_item(
        table_name=_CHANNELS_TABLE,
        key={"channel_id": channel_data.channel_id},
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"頻道 {channel_data.channel_id} 已存在",
        )

    created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    new_channel: dict = {
        "channel_id": channel_data.channel_id,
        "channel_name": channel_data.channel_name,
        "channel_url": channel_data.channel_url,
        "created_at": created_at,
    }

    put_item(table_name=_CHANNELS_TABLE, item=new_channel)

    return ChannelResponse(
        channel_id=channel_data.channel_id,
        channel_name=channel_data.channel_name,
        channel_url=channel_data.channel_url,
        created_at=created_at,
    )


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    _admin: dict = Depends(get_current_admin),
) -> list[ChannelResponse]:
    """
    列出所有頻道白名單（需管理員 JWT）。

    使用 scan_table 全表掃描，頻道數量小規模（預期 < 100 筆）可接受，
    避免引入不必要的 GSI 設計複雜度。
    """
    items = scan_table(_CHANNELS_TABLE)
    return [_to_channel_response(item) for item in items]


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    update_data: ChannelUpdate,
    _admin: dict = Depends(get_current_admin),
) -> ChannelResponse:
    """
    更新頻道資訊（需管理員 JWT）。

    先確認頻道存在，不存在回傳 404 避免誤操作；
    只更新 update_data 中有傳入（非 None）的欄位，
    其餘欄位維持原值，符合 PATCH 語意。
    """
    existing = get_item(
        table_name=_CHANNELS_TABLE,
        key={"channel_id": channel_id},
    )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"頻道 {channel_id} 不存在",
        )

    # 只更新有傳入的欄位
    update_fields: dict = {}
    if update_data.channel_name is not None:
        update_fields["channel_name"] = update_data.channel_name
    if update_data.channel_url is not None:
        update_fields["channel_url"] = update_data.channel_url

    if not update_fields:
        # 無任何欄位更新時直接回傳現有資料
        return _to_channel_response(existing)

    updated = update_item(
        table_name=_CHANNELS_TABLE,
        key={"channel_id": channel_id},
        update_fields=update_fields,
    )

    return _to_channel_response(updated or existing)


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    """
    刪除頻道並串聯取消所有相關訂閱（需管理員 JWT）。

    串聯流程（同步執行於單次請求）：
    1. 確認頻道存在（GetItem），不存在回傳 404
    2. 以 channel_id-index GSI 查詢所有訂閱此頻道的記錄
    3. 對每筆訂閱的 recipient_email 呼叫 send_admin_removed_email（Lambda 環境無 gmail_sender 時略過）
    4. 批次刪除訂閱記錄（逐一 delete_item，小規模可接受）
    5. 刪除頻道記錄
    6. 回傳被取消的訂閱數量
    """
    existing = get_item(
        table_name=_CHANNELS_TABLE,
        key={"channel_id": channel_id},
    )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"頻道 {channel_id} 不存在",
        )

    channel_name: str = existing.get("channel_name", channel_id)
    channel_url: str = existing.get("channel_url", "")

    # 查詢所有訂閱此頻道的記錄
    subscriptions = query_by_gsi_partition(
        table_name=_SUBSCRIPTIONS_TABLE,
        index_name="channel_id-index",
        partition_key_name="channel_id",
        partition_key_value=channel_id,
    )

    # 對每筆訂閱寄送管理員移除通知信（Lambda 環境中 gmail_sender 不存在，略過）
    for sub in subscriptions:
        recipient_email: str = sub.get("recipient_email", "")
        if recipient_email and _send_admin_removed_email is not None:
            try:
                _send_admin_removed_email(
                    recipient_email=recipient_email,
                    channel_name=channel_name,
                    channel_url=channel_url,
                )
            except Exception:
                # 寄信失敗不中斷刪除流程，確保頻道與訂閱資料一定被清除
                pass

    # 批次刪除訂閱記錄
    for sub in subscriptions:
        sub_id: str = sub.get("id", "")
        if sub_id:
            delete_item(
                table_name=_SUBSCRIPTIONS_TABLE,
                key={"id": sub_id},
            )

    # 刪除頻道記錄
    delete_item(
        table_name=_CHANNELS_TABLE,
        key={"channel_id": channel_id},
    )

    return {
        "message": "deleted",
        "cancelled_subscriptions": len(subscriptions),
    }
