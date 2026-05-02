"""
訂閱資料 Pydantic 模型模組。

定義訂閱相關 API 的 Request/Response schema，
包含建立、更新與查詢三種用途的模型。
audio_speed 與 send_time 的業務規則驗證集中在此，
確保無效值不進入 DynamoDB。
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class SubscriptionCreate(BaseModel):
    """
    新增訂閱請求模型。

    channel_url 與 channel_id 由前端呼叫 /channels/verify 後取得，
    audio_speed 必須為 0.5, 1.0, 1.5, 2.0 其中之一（步進 0.5）。
    send_time 格式為 HH:MM（UTC），前端顯示時需自行轉換為本地時間。
    """

    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: EmailStr
    audio_speed: float
    send_time: str

    @field_validator("audio_speed")
    @classmethod
    def validate_audio_speed(cls, v: float) -> float:
        """驗證語速倍率必須為允許值之一，防止無效的音訊處理參數。"""
        allowed_speeds = {0.5, 0.75, 0.85, 1.0, 1.5, 2.0}
        if v not in allowed_speeds:
            raise ValueError(f"audio_speed 必須為 {sorted(allowed_speeds)} 其中之一")
        return v

    @field_validator("send_time")
    @classmethod
    def validate_send_time(cls, v: str) -> str:
        """
        驗證發送時間格式為 HH:MM（00:00 ～ 23:59）。
        確保排程器能正確解析時間，避免無效時間進入資料庫。
        """
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("send_time 格式必須為 HH:MM")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            raise ValueError("send_time 必須為數字格式（例：14:30）")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("send_time 時間範圍為 00:00 ~ 23:59")
        # 正規化為兩位數格式
        return f"{hour:02d}:{minute:02d}"


class SubscriptionUpdate(BaseModel):
    """
    修改訂閱請求模型（所有欄位皆為可選）。

    使用 Optional 允許部分更新（PATCH 語意），
    只傳入需要修改的欄位，未傳入的欄位保持原值。
    """

    recipient_email: Optional[EmailStr] = None
    audio_speed: Optional[float] = None
    send_time: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("audio_speed")
    @classmethod
    def validate_audio_speed(cls, v: Optional[float]) -> Optional[float]:
        """修改時若傳入 audio_speed，同樣驗證允許值。"""
        if v is None:
            return v
        allowed_speeds = {0.5, 0.75, 0.85, 1.0, 1.5, 2.0}
        if v not in allowed_speeds:
            raise ValueError(f"audio_speed 必須為 {sorted(allowed_speeds)} 其中之一")
        return v

    @field_validator("send_time")
    @classmethod
    def validate_send_time(cls, v: Optional[str]) -> Optional[str]:
        """修改時若傳入 send_time，同樣驗證格式。"""
        if v is None:
            return v
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("send_time 格式必須為 HH:MM")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            raise ValueError("send_time 必須為數字格式（例：14:30）")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("send_time 時間範圍為 00:00 ~ 23:59")
        return f"{hour:02d}:{minute:02d}"


class SubscriptionResponse(BaseModel):
    """
    訂閱查詢回應模型。

    包含完整的訂閱資訊，audio_speed 以 float 型別回傳，
    前端顯示時可直接使用，不需額外轉換。
    """

    id: str
    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: str
    audio_speed: float
    send_time: str
    is_active: bool
    created_at: str
