"""
FastAPI 依賴注入模組。

定義 get_current_user 與 get_current_admin 依賴函式，
供需要認證的路由使用。
透過 FastAPI Depends 機制自動從 Authorization header 提取 Bearer token，
解析 JWT 並取得當前用戶資訊，統一在此處理 401/403 回應。

分離認證邏輯到 dependencies.py 的目的：
- 避免各路由重複撰寫 token 解析程式碼
- 讓路由函式保持簡潔，只處理業務邏輯
- 方便測試時以 dependency_overrides 替換認證邏輯
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.auth_service import decode_access_token

# HTTPBearer 自動從 Authorization: Bearer <token> header 提取 token
# auto_error=True 表示若 header 不存在直接回傳 403
_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI 依賴函式：解析 Bearer token 並回傳當前用戶資訊。

    解析失敗（token 無效、過期、格式錯誤）時統一回傳 401 Unauthorized，
    不揭露具體失敗原因，避免資訊洩漏。

    成功時回傳包含 user_id 與 email 的 dict，供路由函式使用：
    {
        "user_id": "uuid-v4",
        "email": "user@example.com"
    }
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 無效或已過期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload 不完整",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"user_id": user_id, "email": email}


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI 依賴函式：驗證 Bearer token 並確認持有者為管理員。

    先以 decode_access_token 驗證 token 有效性（無效/過期 → 401），
    再檢查 payload 中是否包含 is_admin=True 旗標（缺失 → 403）。
    此設計讓一般用戶持有合法 token 時仍無法存取管理員端點，
    同時又能清楚區分「token 無效」與「權限不足」兩種錯誤。

    成功時回傳：
    {
        "user_id": "admin",
        "email": "admin@example.com",
        "is_admin": True
    }
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 無效或已過期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not payload.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限",
        )

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "is_admin": True,
    }
