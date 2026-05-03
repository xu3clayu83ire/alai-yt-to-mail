# yt-to-mail-step10：v3 後端公開訂閱 API

## 前提條件與相依 Step

- **先決條件**：step9 已完成（Lambda Function URL 運行中，subscriptions 表與 GSI 已存在）
- **相依關係**：無，可與 step15 完全平行開始
- **後續相依**：step12、step13 的前端公開頁面需等本 step 完成後整合測試

---

## 功能名稱

後端公開訂閱 API：`POST /public/subscribe`、`GET /public/subscriptions`、`DELETE /public/subscriptions/{id}`

---

## 目標

新增三個無需 JWT 的公開端點，允許：
1. 任何人提交訂閱（recipient_email 直接作為 user_id 儲存）
2. 透過 email 查詢自己的訂閱清單
3. 透過 email 取消特定訂閱

同時更新訂閱資料模型，加入 `auto_cancel_days` 欄位，並擴充現有 `/subscriptions` 路由的 Pydantic 模型以支援此欄位。

---

## 技術規格

### 影響檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `lambda/api/routers/public.py` | **新增** | 公開端點路由 |
| `lambda/api/models/subscription.py` | **修改** | 加入 auto_cancel_days 欄位 |
| `lambda/api/main.py` | **修改** | 掛載 public router |

---

### AWS 服務與資源

- **DynamoDB**：`yt-to-mail-subscriptions` 表（已存在），Schema-less 新增欄位，不變更 Key Schema
  - 新增欄位 `auto_cancel_days`（Number，儲存為 Decimal，預設 3）
  - 新增欄位 `no_new_video_days`（Number，初始值 0，由 step15 排程器維護）
- **Lambda Function**：`yt-to-mail-api`（已存在），不需重新部署基礎設施，只更新程式碼

---

### API 介面

#### POST /public/subscribe

```
HTTP POST /public/subscribe
Content-Type: application/json
Authorization: 不需要
```

**Request Body**：

```json
{
  "recipient_email": "user@example.com",
  "channel_url": "https://www.youtube.com/@channelname",
  "audio_speed": 1.0,
  "send_time": "14:00",
  "auto_cancel_days": 3
}
```

**欄位規則**：
- `recipient_email`：EmailStr，必填
- `channel_url`：str，必填
- `audio_speed`：float，必填，範圍 0.5–2.0
- `send_time`：str，必填，格式 `HH:MM`（UTC）
- `auto_cancel_days`：int，必填，min=1，預設 3

**處理邏輯**：
1. 以 `recipient_email` 作為 `user_id`（不建立 users 表記錄）
2. 呼叫 `/channels/verify` 邏輯驗證 channel_url，取得 channel_id 與 channel_name（複用現有 `channels.py` 的解析函式）
3. 查詢 `user_id-index` GSI，驗證此 email 的訂閱數量 < 5
4. 新增訂閱，包含 `auto_cancel_days` 與 `no_new_video_days=0`

**Response（201 Created）**：

```json
{
  "id": "uuid-v4",
  "channel_name": "Channel Name",
  "channel_url": "https://...",
  "recipient_email": "user@example.com",
  "audio_speed": 1.0,
  "send_time": "14:00",
  "auto_cancel_days": 3,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**Error 回應**：
- `400`：訂閱數量已達上限（最多 5 個）
- `400`：無法解析頻道 URL（channel_url 無效）
- `422`：欄位驗證失敗（格式錯誤）

---

#### GET /public/subscriptions?email=xxx

```
HTTP GET /public/subscriptions?email=user@example.com
Authorization: 不需要
```

**處理邏輯**：
1. 以 `email` query param 作為 `user_id` 查詢 `user_id-index` GSI
2. 回傳該 email 的所有訂閱（含 `no_new_video_days` 與 `auto_cancel_days`）

**Response（200 OK）**：

```json
[
  {
    "id": "uuid-v4",
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

**Error 回應**：
- `422`：email query param 缺失或格式錯誤

---

#### DELETE /public/subscriptions/{id}?email=xxx

```
HTTP DELETE /public/subscriptions/{id}?email=user@example.com
Authorization: 不需要
```

**處理邏輯**：
1. 以 `id` 取得訂閱項目
2. 驗證 `subscription.user_id == email`（防止他人刪除）
3. 刪除訂閱

**Response（200 OK）**：`{"message": "deleted"}`

**Error 回應**：
- `404`：訂閱不存在
- `403`：email 與訂閱擁有者不符

---

### Pydantic 模型更新（models/subscription.py）

**新增 `PublicSubscriptionCreate`**：

```python
class PublicSubscriptionCreate(BaseModel):
    recipient_email: EmailStr
    channel_url: str
    audio_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    send_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    auto_cancel_days: int = Field(default=3, ge=1)
```

**修改 `SubscriptionCreate`**（現有私有 API 也支援 auto_cancel_days）：

```python
class SubscriptionCreate(BaseModel):
    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: EmailStr
    audio_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    send_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    auto_cancel_days: int = Field(default=3, ge=1)  # 新增
```

**修改 `SubscriptionResponse`**（加入新欄位）：

```python
class SubscriptionResponse(BaseModel):
    id: str
    channel_url: str
    channel_id: str
    channel_name: str
    recipient_email: str
    audio_speed: float
    send_time: str
    is_active: bool
    auto_cancel_days: int = 3   # 新增
    no_new_video_days: int = 0  # 新增
    created_at: str
```

**新增 `PublicSubscriptionResponse`**（不含 channel_id）：

```python
class PublicSubscriptionResponse(BaseModel):
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
```

---

### main.py 修改（掛載 public router）

```python
# 在現有路由掛載後加入
from routers import public
app.include_router(public.router, prefix="/public", tags=["public"])
```

---

### routers/public.py 結構示意

```python
"""
公開訂閱路由模組（無 JWT 認證）
提供：POST /public/subscribe, GET /public/subscriptions, DELETE /public/subscriptions/{id}
"""

router = APIRouter()

@router.post("/subscribe", response_model=PublicSubscriptionResponse, status_code=201)
async def public_subscribe(sub_data: PublicSubscriptionCreate) -> PublicSubscriptionResponse:
    """
    公開訂閱端點，無需 JWT 認證。
    以 recipient_email 作為 user_id 儲存，呼叫 channels.py 驗證 channel_url。
    """
    ...

@router.get("/subscriptions", response_model=list[PublicSubscriptionResponse])
async def public_list_subscriptions(email: str = Query(...)) -> list[PublicSubscriptionResponse]:
    """
    透過 email 查詢訂閱清單，利用 user_id-index GSI。
    """
    ...

@router.delete("/subscriptions/{subscription_id}")
async def public_delete_subscription(
    subscription_id: str,
    email: str = Query(...),
) -> dict:
    """
    透過 email 驗證擁有者後刪除訂閱。
    """
    ...
```

---

### 頻道 URL 驗證邏輯複用

`public_subscribe` 需要取得 `channel_id` 與 `channel_name`。應將 `routers/channels.py` 中的 channel 解析邏輯抽取為共用函式（或直接呼叫 `channels.py` 中已有的 helper function）：

- 若 `channels.py` 已有私有 helper，直接 import 使用
- 若邏輯內嵌在路由函式內，需先重構為可呼叫的函式

---

### IAM 權限

無需額外 IAM 變更，沿用現有 Lambda 執行角色。

### 環境變數

無需新增。

---

## 驗收標準

- [ ] `POST /public/subscribe` 成功新增訂閱，response 包含 `auto_cancel_days`
- [ ] `POST /public/subscribe` 第 6 個訂閱回傳 400
- [ ] `POST /public/subscribe` 無效 channel_url 回傳 400
- [ ] `GET /public/subscriptions?email=xxx` 正確回傳該 email 的訂閱清單
- [ ] `DELETE /public/subscriptions/{id}?email=xxx` 正確刪除訂閱
- [ ] `DELETE /public/subscriptions/{id}?email=wrong` 回傳 403
- [ ] 所有端點無需 Authorization header 即可呼叫
- [ ] 現有私有 API（GET/POST/PUT/DELETE /subscriptions）不受影響
- [ ] `SubscriptionResponse` 含 `auto_cancel_days` 與 `no_new_video_days` 欄位（向後相容，舊資料預設 3 / 0）
- [ ] tsc + jest + cdk synth 全部通過（僅 Python 程式碼修改，CDK 不受影響）

---

## 工作分派

### 本 Step 指派
- **Coder A**（後端軌道）：負責本 step 全部內容

### 平行協作
- **Coder B** 可同時執行 **step15**（排程器自動取消，完全獨立）

---

## 注意事項與限制

- `user_id` 欄位直接存 email 字串，與現有 JWT 用戶（user_id 為 UUID）邏輯並存，不衝突
- `no_new_video_days` 欄位僅由排程器（step15）維護，本 step 只在新增時寫入預設值 0
- 舊有訂閱（無 `auto_cancel_days` 欄位）在 GET 回傳時以 Pydantic 預設值 3 填充，不需要 backfill DynamoDB
- 所有函式必須包含繁體中文函式級註解
- 禁止使用 `any` 型別，所有 Python type hints 正確標注
