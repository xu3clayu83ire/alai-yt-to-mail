"""
頻道資料模型模組。

定義管理員頻道白名單 CRUD 操作所需的 Pydantic 模型，
以及公開頻道列表端點使用的回應模型。

分離 ChannelResponse（含 created_at）與 PublicChannelResponse（不含 created_at）的原因：
前端下拉選單不需要 created_at 欄位，減少不必要的資料傳輸；
管理員後台需要 created_at 以排序與稽核用途。
"""

from typing import Optional

from pydantic import BaseModel


class ChannelCreate(BaseModel):
    """
    新增頻道請求模型。

    channel_id 使用 YouTube handle 或 channel ID（UCxxx），
    作為 DynamoDB Partition Key，確保同一頻道不重複建立。
    """

    channel_id: str           # YouTube handle 或 channel ID
    channel_name: str
    channel_url: str


class ChannelUpdate(BaseModel):
    """
    更新頻道請求模型（所有欄位皆為選填）。

    PATCH 語意：只更新有傳入的欄位，未傳入的欄位保持不變，
    避免前端每次都要送出完整物件。
    """

    channel_name: Optional[str] = None
    channel_url: Optional[str] = None


class ChannelResponse(BaseModel):
    """
    頻道回應模型（管理員用）。

    包含 created_at 供管理員後台排序與稽核，
    不向公開端點揭露此欄位以降低回應資料量。
    """

    channel_id: str
    channel_name: str
    channel_url: str
    created_at: str


class PublicChannelResponse(BaseModel):
    """
    公開頻道回應模型（前端下拉選單用）。

    不含 created_at，前端下拉選單只需 channel_id / channel_name / channel_url
    即可完成選項呈現與訂閱建立，減少不必要的資料傳輸。
    """

    channel_id: str
    channel_name: str
    channel_url: str
