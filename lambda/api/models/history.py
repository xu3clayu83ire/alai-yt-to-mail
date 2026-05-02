"""
歷史紀錄 Pydantic 模型模組。

定義歷史紀錄查詢的回應 schema。
歷史紀錄為唯讀資源（由排程器寫入，前端只查詢），
因此只有 Response 模型，沒有 Create/Update 模型。
"""

from typing import Optional

from pydantic import BaseModel


class HistoryResponse(BaseModel):
    """
    歷史紀錄查詢回應模型。

    error_message 為可選欄位，只在 status=failed 時存在，
    status 為列舉字串：done / failed / skipped_language，
    與排程器寫入 DynamoDB 的值保持一致。
    """

    id: str
    subscription_id: str
    video_id: str
    video_title: str
    sent_at: str
    status: str
    error_message: Optional[str] = None
