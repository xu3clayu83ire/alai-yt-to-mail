"""
訂閱資料 Pydantic 模型模組。

定義訂閱相關 API 的 Request/Response schema，
包含建立、更新與查詢三種用途的模型。
audio_speed 與 send_time 的業務規則驗證集中在此，
確保無效值不進入 DynamoDB。
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class SubscriptionCreate(BaseModel):
    """
    新增訂閱請求模型（需 JWT 認證）。

    channel_url 與 channel_id 由前端呼叫 /channels/verify 後取得，
    audio_speed 必須為 0.5, 1.0, 1.5, 2.0 其中之一（步進 0.5）。
    send_time 格式為 HH:MM（UTC），前端顯示時需自行轉換為本地時間。
    auto_cancel_days 為連續無新影片天數觸發自動取消的閾值。
    """

    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: EmailStr
    audio_speed: float
    send_time: str
    auto_cancel_days: int = Field(default=3, ge=1)  # 連續無新影片幾天後自動取消訂閱

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
    訂閱查詢回應模型（需 JWT 認證的端點使用）。

    包含完整的訂閱資訊，audio_speed 以 float 型別回傳，
    前端顯示時可直接使用，不需額外轉換。
    auto_cancel_days 與 no_new_video_days 為 v3 新增欄位，
    舊資料可能不存在，由呼叫端以 .get() 提供預設值。
    """

    id: str
    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: str
    audio_speed: float
    send_time: str
    is_active: bool
    auto_cancel_days: int = 3   # 連續無新影片幾天後自動取消，舊資料預設 3
    no_new_video_days: int = 0  # 目前連續無新影片天數，舊資料預設 0
    created_at: str


class PublicSubscriptionCreate(BaseModel):
    """
    公開訂閱請求模型（無需 JWT 認證）。

    以 recipient_email 作為身份識別（user_id），
    不依賴 users 資料表，讓未註冊用戶也能直接訂閱。
    channel_url 會在後端重新解析取得 channel_id / channel_name，
    降低前端須先呼叫 /channels/verify 的門檻。
    """

    recipient_email: EmailStr
    channel_url: str
    audio_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    send_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    auto_cancel_days: int = Field(default=3, ge=1)


class PublicSubscriptionResponse(BaseModel):
    """
    公開訂閱查詢回應模型（不含 channel_id，避免暴露內部 ID）。

    供無 JWT 的前端頁面顯示訂閱清單使用，
    只包含用戶可見的資訊，不包含 user_id 等內部欄位。
    """

    id: str
    channel_url: str
    channel_name: str
    recipient_email: str
    audio_speed: float
    send_time: str
    is_active: bool
    auto_cancel_days: int = 3
    no_new_video_days: int = 0
    created_at: str


class AdminSubscriptionResponse(BaseModel):
    """
    管理員訂閱查詢回應模型（含 user_id，供後台管理使用）。

    相較於 SubscriptionResponse，額外包含 user_id 欄位，
    讓管理員能追蹤每筆訂閱歸屬於哪位用戶，
    方便跨用戶查詢與強制刪除操作。
    auto_cancel_days / no_new_video_days 為 v3 新增欄位，
    舊資料可能不存在，由呼叫端以 .get() 提供預設值。
    """

    id: str
    user_id: str
    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: str
    audio_speed: float
    send_time: str
    is_active: bool
    auto_cancel_days: int = 3
    no_new_video_days: int = 0
    created_at: str
