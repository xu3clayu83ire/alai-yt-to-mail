"""
認證服務模組。

集中管理 bcrypt 密碼雜湊與驗證、JWT 產生與解析邏輯。
JWT_SECRET_KEY 必須從環境變數讀取，禁止硬編碼，
以確保不同環境（開發/生產）使用不同密鑰，降低洩漏風險。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

# 從環境變數讀取 JWT 設定
# 若 JWT_SECRET_KEY 未設定或為空，將在 create_token 時拋出例外，
# 強制要求部署時必須正確設定環境變數。
_JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
_JWT_EXPIRE_HOURS: int = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))
_JWT_ALGORITHM: str = "HS256"


def hash_password(plain_password: str) -> str:
    """
    使用 bcrypt 雜湊純文字密碼。

    rounds=12 提供足夠的計算成本，平衡安全性與效能：
    - 低於 10 rounds 在現代硬體上可快速暴力破解
    - 高於 14 rounds 在 Lambda 30s timeout 內可能超時
    設定為 12 是業界推薦的最小生產級別。
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    驗證純文字密碼與 bcrypt 雜湊值是否相符。

    使用 bcrypt 內建的 constant-time 比較，
    防止 timing attack（計時攻擊）洩漏密碼正確性資訊。
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(user_id: str, email: str) -> str:
    """
    產生 JWT access token。

    Payload 包含 sub（user_id）、email、iat（簽發時間）、exp（過期時間）。
    使用 HS256 對稱加密演算法，密鑰從環境變數讀取，
    過期時間由 JWT_EXPIRE_HOURS 環境變數控制（預設 24 小時）。

    若 JWT_SECRET_KEY 為空，主動拋出例外而非產生不安全的 token。
    """
    if not _JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY 環境變數未設定，無法產生 JWT token")

    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(hours=_JWT_EXPIRE_HOURS)

    payload: dict = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(payload, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    解析並驗證 JWT token，回傳 payload dict。

    若 token 已過期、簽名無效或格式錯誤，回傳 None，
    由呼叫方（dependencies.py）統一回傳 401 Unauthorized。
    不在此處直接拋出 HTTPException，以保持服務層的可測試性。
    """
    if not _JWT_SECRET_KEY:
        return None

    try:
        payload = jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
