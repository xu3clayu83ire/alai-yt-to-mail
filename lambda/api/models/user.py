"""
用戶資料 Pydantic 模型模組。

定義用戶相關 API 的 Request/Response schema，
使用 Pydantic v2 驗證規則確保 email 格式與密碼長度符合規格。
UserResponse 不包含 password_hash 欄位，避免敏感資訊洩漏至 API 回應。
"""

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    """
    用戶註冊請求模型。

    email 使用 EmailStr 自動驗證格式（需安裝 pydantic[email]）。
    password 長度 ≥ 8 字元驗證由 field_validator 強制執行，
    比依賴前端驗證更安全，防止繞過前端直接呼叫 API。
    """

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """驗證密碼長度不得少於 8 個字元，符合基本安全要求。"""
        if len(v) < 8:
            raise ValueError("密碼長度必須至少 8 個字元")
        return v


class UserLogin(BaseModel):
    """
    用戶登入請求模型。

    登入不需要密碼長度驗證（後端以 bcrypt 比對），
    分離 UserCreate 與 UserLogin 避免混淆各自的驗證規則。
    """

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """
    用戶 API 回應模型。

    只暴露 id、email、created_at 三個欄位，
    絕對不包含 password_hash，確保密碼雜湊不外洩。
    """

    id: str
    email: str
    created_at: str
