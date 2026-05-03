"""
認證路由模組。

提供用戶註冊（/auth/register）與登入（/auth/login）兩個端點。
密碼驗證失敗時統一回傳 401，不揭露是 email 不存在還是密碼錯誤，
防止用戶枚舉（user enumeration）攻擊。

email 已存在時回傳 409 Conflict，
讓前端能區分「帳號已被使用」與「其他格式錯誤」的情境。

管理員登入路徑優先判斷（不查 DynamoDB），
憑證從環境變數讀取，不儲存於資料庫，
以利緊急情況下直接修改環境變數即可禁用管理員存取。
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from models.user import UserCreate, UserLogin, UserResponse
from services.auth_service import create_access_token, hash_password, verify_password
from services.dynamo_service import get_item, put_item, query_by_gsi_partition

router = APIRouter()

_USERS_TABLE: str = os.environ.get("USERS_TABLE", "yt-to-mail-users")

# 管理員憑證從環境變數讀取，絕不硬編碼於程式碼中，
# 部署時透過 CDK Stack Props 注入（adminEmail / adminPasswordHash）
_ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "")
_ADMIN_PASSWORD_HASH: str = os.environ.get("ADMIN_PASSWORD_HASH", "")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate) -> UserResponse:
    """
    用戶註冊端點。

    先透過 email-index GSI 查詢 email 是否已存在，
    避免重複建立相同 email 的帳號。
    密碼以 bcrypt rounds=12 雜湊後儲存，絕對不儲存明文密碼。
    回傳 201 Created 與新用戶資料（不含 password_hash）。
    """
    # 以 email-index GSI 檢查 email 是否已被註冊
    existing_users = query_by_gsi_partition(
        table_name=_USERS_TABLE,
        index_name="email-index",
        partition_key_name="email",
        partition_key_value=str(user_data.email),
    )

    if existing_users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="此 Email 已被使用",
        )

    # 建立新用戶資料
    user_id = str(uuid.uuid4())
    created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    password_hash = hash_password(user_data.password)

    new_user = {
        "id": user_id,
        "email": str(user_data.email),
        "password_hash": password_hash,
        "created_at": created_at,
    }

    put_item(table_name=_USERS_TABLE, item=new_user)

    return UserResponse(
        id=user_id,
        email=str(user_data.email),
        created_at=created_at,
    )


@router.post("/login")
async def login(user_data: UserLogin) -> dict:
    """
    用戶登入端點。

    管理員路徑優先判斷：若 email 符合 ADMIN_EMAIL 環境變數，
    直接以 bcrypt 驗證 ADMIN_PASSWORD_HASH，不查詢 DynamoDB，
    避免管理員憑證與一般用戶資料表耦合。

    一般用戶走原有邏輯：以 email-index GSI 查詢後驗證密碼。
    驗證失敗時統一回傳 401，不區分「帳號不存在」與「密碼錯誤」，
    防止用戶枚舉攻擊。
    成功時回傳 JWT access token，過期時間 24 小時。
    """
    # 管理員路徑優先判斷（不查 DynamoDB），
    # 只有在 ADMIN_EMAIL 環境變數有值且 email 相符時才進入此分支
    if _ADMIN_EMAIL and str(user_data.email) == _ADMIN_EMAIL:
        if not _ADMIN_PASSWORD_HASH or not verify_password(user_data.password, _ADMIN_PASSWORD_HASH):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="帳號或密碼錯誤",
                headers={"WWW-Authenticate": "Bearer"},
            )
        admin_token = create_access_token(
            user_id="admin",
            email=_ADMIN_EMAIL,
            is_admin=True,
        )
        return {
            "access_token": admin_token,
            "token_type": "bearer",
            "expires_in": int(os.environ.get("JWT_EXPIRE_HOURS", "24")) * 3600,
        }

    # 一般用戶：以 email-index GSI 查詢用戶
    users = query_by_gsi_partition(
        table_name=_USERS_TABLE,
        index_name="email-index",
        partition_key_name="email",
        partition_key_value=str(user_data.email),
    )

    # 統一使用相同的 401 錯誤訊息，不洩露具體失敗原因
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email 或密碼錯誤",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not users:
        raise auth_error

    user = users[0]

    # 驗證密碼（bcrypt constant-time 比較）
    if not verify_password(user_data.password, user["password_hash"]):
        raise auth_error

    # 產生 JWT token
    access_token = create_access_token(
        user_id=user["id"],
        email=user["email"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": int(os.environ.get("JWT_EXPIRE_HOURS", "24")) * 3600,
    }
