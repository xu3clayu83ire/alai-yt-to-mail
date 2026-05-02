"""
歷史紀錄路由模組。

提供查詢當前用戶的排程執行歷史紀錄（GET /history）。
支援 limit 與 subscription_id 兩個 query 參數，
允許前端分頁載入或篩選特定訂閱的歷史。

所有查詢都以 user_id 為 GSI partition key，
確保用戶無法存取他人的歷史紀錄。
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, Query
from boto3.dynamodb.conditions import Attr, Key

from dependencies import get_current_user
from models.history import HistoryResponse
from services.dynamo_service import query_by_index

router = APIRouter()

_HISTORY_TABLE: str = os.environ.get("HISTORY_TABLE", "yt-to-mail-history")
_DEFAULT_LIMIT: int = 20
_MAX_LIMIT: int = 100


@router.get("", response_model=list[HistoryResponse])
async def list_history(
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="回傳筆數上限"),
    subscription_id: Optional[str] = Query(default=None, description="篩選特定訂閱 ID"),
    current_user: dict = Depends(get_current_user),
) -> list[HistoryResponse]:
    """
    取得當前用戶的歷史紀錄。

    以 user_id-index GSI 查詢（Partition Key: user_id, Sort Key: sent_at），
    設定 scan_index_forward=False 實現時間降冪排序（最新紀錄優先）。
    若指定 subscription_id，使用 FilterExpression 在查詢結果中篩選，
    注意 FilterExpression 在 Limit 之後執行，
    實際回傳筆數可能少於 limit（DynamoDB 的 Limit 是掃描上限而非回傳上限）。
    """
    key_condition = Key("user_id").eq(current_user["user_id"])
    filter_expression = None

    if subscription_id:
        filter_expression = Attr("subscription_id").eq(subscription_id)

    items = query_by_index(
        table_name=_HISTORY_TABLE,
        index_name="user_id-index",
        key_condition=key_condition,
        filter_expression=filter_expression,
        limit=limit,
        scan_index_forward=False,  # 降冪排序：最新紀錄排在前面
    )

    return [
        HistoryResponse(
            id=item["id"],
            subscription_id=item["subscription_id"],
            video_id=item["video_id"],
            video_title=item["video_title"],
            sent_at=item["sent_at"],
            status=item["status"],
            error_message=item.get("error_message"),
        )
        for item in items
    ]
