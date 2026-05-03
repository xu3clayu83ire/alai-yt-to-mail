# yt-to-mail-step11：v3 後端管理員 API

## 前提條件與相依 Step

- **先決條件**：step10 已完成（public 路由已掛載，模型已更新）
- **相依關係**：必須在 step10 之後執行（Coder A 軌道，依序）
- **後續相依**：step14（前端管理員後台）需等本 step 完成後整合測試

---

## 功能名稱

後端管理員 API：admin login 判斷 + `GET /admin/subscriptions` + `DELETE /admin/subscriptions/{id}` + CDK 環境變數更新

---

## 目標

1. 擴充 `POST /auth/login`，當 email == `ADMIN_EMAIL` 且密碼驗證通過時，JWT payload 加入 `is_admin: true`
2. 新增 admin 專用 dependency（`get_current_admin`），驗證 JWT 含 `is_admin: true`
3. 新增 `GET /admin/subscriptions`（Scan 全表，支援 email 篩選）
4. 新增 `DELETE /admin/subscriptions/{id}`（無 user_id 驗證，admin 可刪除任何訂閱）
5. CDK BackendStack 加入 `ADMIN_EMAIL`、`ADMIN_PASSWORD_HASH` 環境變數，從 CDK Context 讀取

---

## 技術規格

### 影響檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `lambda/api/routers/auth.py` | **修改** | login 加入 admin 判斷 |
| `lambda/api/services/auth_service.py` | **修改** | create_access_token 加入 is_admin 參數 |
| `lambda/api/dependencies.py` | **修改** | 新增 get_current_admin 依賴函式 |
| `lambda/api/routers/admin.py` | **新增** | admin 路由 |
| `lambda/api/main.py` | **修改** | 掛載 admin router |
| `lib/yt-to-mail-backend-stack.ts` | **修改** | 加入 ADMIN_EMAIL、ADMIN_PASSWORD_HASH 環境變數 |
| `bin/yt-to-mail.ts` | **修改** | 從 CDK Context 讀取 adminEmail、adminPasswordHash |

---

### AWS 服務與資源

- **Lambda Function**：`yt-to-mail-api`（已存在），新增環境變數
  - `ADMIN_EMAIL`：從 CDK Context `adminEmail` 讀取
  - `ADMIN_PASSWORD_HASH`：從 CDK Context `adminPasswordHash` 讀取（bcrypt 雜湊字串）
- **DynamoDB**：`yt-to-mail-subscriptions` 表（已存在），新增 Scan 操作（已有權限）

---

### CDK Stack 更新規格

**YtToMailBackendStackProps 擴充**：

```typescript
interface YtToMailBackendStackProps extends cdk.StackProps {
  allowedOrigin?: string;
  adminEmail?: string;        // 新增
  adminPasswordHash?: string; // 新增
}
```

**Lambda 環境變數新增**：

```typescript
environment: {
  // ...現有環境變數...
  ADMIN_EMAIL: props?.adminEmail ?? '',
  ADMIN_PASSWORD_HASH: props?.adminPasswordHash ?? '',
}
```

**bin/yt-to-mail.ts 更新**：

```typescript
new YtToMailBackendStack(app, 'YtToMailBackendStack', {
  allowedOrigin: app.node.tryGetContext('allowedOrigin') ?? '*',
  adminEmail: app.node.tryGetContext('adminEmail') ?? '',
  adminPasswordHash: app.node.tryGetContext('adminPasswordHash') ?? '',
});
```

**部署指令示意**：

```powershell
npx cdk deploy YtToMailBackendStack `
  --context adminEmail=admin@example.com `
  --context adminPasswordHash='$2b$12$...'
```

---

### auth_service.py 更新

**`create_access_token` 加入 `is_admin` 參數**：

```python
def create_access_token(user_id: str, email: str, is_admin: bool = False) -> str:
    """
    產生 JWT access token。
    is_admin=True 時在 payload 加入 is_admin 旗標，
    供 admin 路由的 get_current_admin 依賴函式判斷權限。
    """
    payload: dict = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if is_admin:
        payload["is_admin"] = True
    return jwt.encode(payload, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)
```

---

### auth.py 更新（login admin 判斷）

```python
# 讀取 admin 設定（環境變數，部署時從 CDK Context 注入）
_ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "")
_ADMIN_PASSWORD_HASH: str = os.environ.get("ADMIN_PASSWORD_HASH", "")

@router.post("/login")
async def login(user_data: UserLogin) -> dict:
    """
    用戶登入端點。
    若 email 與 ADMIN_EMAIL 相符，改用 ADMIN_PASSWORD_HASH 驗證，
    驗證通過後回傳含 is_admin=true 的 JWT。
    一般用戶走原有 DynamoDB 驗證邏輯。
    """
    # Admin 路徑：直接以環境變數驗證，不查 DynamoDB
    if _ADMIN_EMAIL and user_data.email == _ADMIN_EMAIL:
        if not _ADMIN_PASSWORD_HASH or not verify_password(user_data.password, _ADMIN_PASSWORD_HASH):
            raise auth_error
        access_token = create_access_token(
            user_id="admin",
            email=_ADMIN_EMAIL,
            is_admin=True,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": int(os.environ.get("JWT_EXPIRE_HOURS", "24")) * 3600,
        }

    # 一般用戶路徑（原有邏輯不變）
    ...
```

---

### dependencies.py 更新（新增 get_current_admin）

```python
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI 依賴函式：驗證 Bearer token 並確認 is_admin=True。
    token 無效或非 admin 時統一回傳 403 Forbidden，
    不回傳 401 以區分「未認證」與「無權限」的語義差異。
    成功時回傳 {"user_id": "admin", "email": "admin@...", "is_admin": True}。
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 無效或已過期")

    if not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理員權限")

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "is_admin": True,
    }
```

---

### API 介面

#### GET /admin/subscriptions

```
HTTP GET /admin/subscriptions
HTTP GET /admin/subscriptions?email=user@example.com
Authorization: Bearer <admin-jwt>
```

**處理邏輯**：
1. 驗證 admin JWT（`get_current_admin`）
2. Scan 全表（`yt-to-mail-subscriptions`）
3. 若有 `email` query param，在 Python 端篩選 `item["user_id"] == email`（或 `item["recipient_email"] == email`）
4. 回傳所有欄位

**Response（200 OK）**：

```json
[
  {
    "id": "uuid-v4",
    "user_id": "user@example.com",
    "channel_name": "Channel Name",
    "channel_url": "https://...",
    "recipient_email": "user@example.com",
    "audio_speed": 1.0,
    "send_time": "14:00",
    "auto_cancel_days": 3,
    "no_new_video_days": 0,
    "is_active": true,
    "created_at": "2026-05-03T10:00:00Z"
  }
]
```

---

#### DELETE /admin/subscriptions/{id}

```
HTTP DELETE /admin/subscriptions/{id}
Authorization: Bearer <admin-jwt>
```

**處理邏輯**：
1. 驗證 admin JWT
2. 取得訂閱（`GetItem`），不存在回傳 404
3. 直接刪除（不驗證 user_id，admin 可刪除任何訂閱）

**Response（200 OK）**：`{"message": "deleted"}`

---

### routers/admin.py 結構示意

```python
"""
管理員路由模組。
所有端點需要 admin JWT（get_current_admin 依賴函式）。
提供：GET /admin/subscriptions（全表查詢+篩選），DELETE /admin/subscriptions/{id}
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from dependencies import get_current_admin
from services.dynamo_service import delete_item, get_item, scan_table
from models.subscription import AdminSubscriptionResponse

router = APIRouter()

@router.get("/subscriptions", response_model=list[AdminSubscriptionResponse])
async def admin_list_subscriptions(
    email: Optional[str] = Query(default=None),
    current_admin: dict = Depends(get_current_admin),
) -> list[AdminSubscriptionResponse]:
    """全表 Scan，可選以 email 篩選（比對 user_id 欄位）"""
    ...

@router.delete("/subscriptions/{subscription_id}")
async def admin_delete_subscription(
    subscription_id: str,
    current_admin: dict = Depends(get_current_admin),
) -> dict:
    """Admin 強制刪除訂閱，不驗證擁有者"""
    ...
```

---

### Pydantic 模型新增（models/subscription.py）

**新增 `AdminSubscriptionResponse`**（含 user_id 欄位）：

```python
class AdminSubscriptionResponse(BaseModel):
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
```

---

### dynamo_service.py 新增函式

目前 `dynamo_service.py` 可能沒有 `scan_table` 函式，需新增：

```python
def scan_table(table_name: str) -> list[dict]:
    """
    對 DynamoDB 資料表執行完整 Scan，處理分頁，回傳所有項目。
    僅限管理員功能使用，一般用戶查詢改用 query_by_gsi_partition。
    """
    ...
```

---

### IAM 權限

無需額外 IAM 變更，現有 `yt-to-mail-dynamodb-policy` 已包含 `dynamodb:Scan`。

---

### 環境變數

| 變數名稱 | 說明 | 來源 |
|---------|------|------|
| `ADMIN_EMAIL` | 管理員 email，登入時觸發 admin 路徑 | CDK Context `adminEmail` |
| `ADMIN_PASSWORD_HASH` | 管理員密碼的 bcrypt 雜湊 | CDK Context `adminPasswordHash` |

**bcrypt hash 產生方式**（供部署參考，不寫入程式碼）：

```python
import bcrypt
print(bcrypt.hashpw(b"your-password", bcrypt.gensalt(rounds=12)).decode())
```

---

## 驗收標準

- [ ] `POST /auth/login` 以 admin email + 正確密碼登入，JWT decode 後含 `is_admin: true`
- [ ] `POST /auth/login` 以一般 email 登入，JWT decode 後不含 `is_admin` 欄位
- [ ] `GET /admin/subscriptions` 以 admin JWT 可取得全表資料
- [ ] `GET /admin/subscriptions?email=xxx` 只回傳該 email 的訂閱
- [ ] `GET /admin/subscriptions` 以一般用戶 JWT 回傳 403
- [ ] `GET /admin/subscriptions` 無 JWT 回傳 401 或 403
- [ ] `DELETE /admin/subscriptions/{id}` 以 admin JWT 可刪除任意訂閱
- [ ] CDK Stack 加入 `ADMIN_EMAIL`、`ADMIN_PASSWORD_HASH` 環境變數
- [ ] `cdk synth` 通過，`tsc --noEmit` 無型別錯誤
- [ ] 若 `ADMIN_EMAIL` 環境變數為空，login 端點仍正常處理一般用戶（不崩潰）

---

## 工作分派

### 本 Step 指派
- **Coder A**（後端軌道）：依序在 step10 完成後執行本 step

### 平行協作
- **Coder B** 在 step15 完成後，可開始 step12（前端公開訂閱頁，需 step10 API）

---

## 注意事項與限制

- `ADMIN_EMAIL` 與 `ADMIN_PASSWORD_HASH` 屬敏感資訊，僅存環境變數，絕不寫入程式碼或版本控制
- Admin login 不查 DynamoDB users 表，減少資料庫存取並避免帳號枚舉
- `scan_table` 效能在小規模（< 1000 訂閱）可接受；未來若規模擴大需改為 Filter + Index
- CDK Context 僅在 `cdk deploy` 指令時傳入，`cdk synth` 時留空字串為正常情況
- 所有函式必須包含繁體中文函式級註解
