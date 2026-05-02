# yt-to-mail-step6：Phase 1 — 雲端後端（Lambda + DynamoDB）

## 功能名稱

雲端後端 API：Lambda Function URL + FastAPI + DynamoDB

---

## 目標

建立 yt-to-mail 系統的雲端後端核心，包含：
- DynamoDB 三張資料表（用戶、訂閱、歷史紀錄）
- 單一 Lambda Function 以 FastAPI + Mangum 提供 RESTful API
- JWT 認證機制
- 訂閱 CRUD（含上限 5 個驗證）
- 歷史紀錄查詢

前端與本機排程器均透過此後端存取資料，是整個系統的資料核心。

---

## 技術規格

### AWS 服務與資源

#### DynamoDB 資料表

**1. users 表**
- 表名稱：`yt-to-mail-users`
- Partition Key：`id`（String，UUID v4）
- 欄位清單：
  - `id`：String，UUID v4，主鍵
  - `email`：String，用戶登入信箱
  - `password_hash`：String，bcrypt 雜湊值（rounds=12）
  - `created_at`：String，ISO 8601 UTC 時間戳記
- GSI：`email-index`
  - Partition Key：`email`（String）
  - 投影模式：ALL
- 計費模式：PAY_PER_REQUEST
- Point-in-time recovery：停用（原型階段）

**2. subscriptions 表**
- 表名稱：`yt-to-mail-subscriptions`
- Partition Key：`id`（String，UUID v4）
- 欄位清單：
  - `id`：String，UUID v4，主鍵
  - `user_id`：String，對應 users.id
  - `channel_url`：String，YouTube 頻道完整 URL
  - `channel_id`：String，YouTube channel_id（由後端解析或前端傳入）
  - `channel_name`：String，頻道名稱（顯示用）
  - `recipient_email`：String，收件信箱
  - `audio_speed`：Number，語速倍率（0.5 ～ 2.0，步進 0.5）
  - `send_time`：String，格式 `HH:MM`，儲存 UTC 時間
  - `is_active`：Boolean，是否啟用，預設 true
  - `created_at`：String，ISO 8601 UTC 時間戳記
- GSI：`user_id-index`
  - Partition Key：`user_id`（String）
  - 投影模式：ALL
- 計費模式：PAY_PER_REQUEST

**3. history 表**
- 表名稱：`yt-to-mail-history`
- Partition Key：`id`（String，UUID v4）
- 欄位清單：
  - `id`：String，UUID v4，主鍵
  - `user_id`：String，對應 users.id
  - `subscription_id`：String，對應 subscriptions.id
  - `video_id`：String，YouTube video ID
  - `video_title`：String，影片標題
  - `sent_at`：String，ISO 8601 UTC 時間戳記
  - `status`：String，列舉值 `done` / `failed` / `skipped_language`（`skipped_duplicate` 不寫入 history）
  - `error_message`：String，可選，失敗時的錯誤訊息
- GSI（現有）：`user_id-index`
  - Partition Key：`user_id`（String）
  - Sort Key：`sent_at`（String）
  - 投影模式：ALL
  - 用途：前端查詢歷史紀錄
- 計費模式：PAY_PER_REQUEST

> **未來優化（規模擴大時）**：新增第二個 GSI 供排程器查詢已寄影片：
> - GSI 名稱：`subscription_id-status-index`
> - Partition Key：`subscription_id`（String）
> - Sort Key：`status`（String）
> - 投影模式：KEYS_ONLY（只需 video_id，節省儲存）
>
> 現行排程器以 `Scan + FilterExpression` 取得已寄影片清單，讀取量為 O(全表)。加入此 GSI 後可改用 `Query`，讀取量降為 O(單一訂閱紀錄數)，適合用戶與訂閱數大幅增長時。

#### Lambda Function

- 函式名稱：`yt-to-mail-api`
- Runtime：`python3.12`
- Architecture：`x86_64`
- 記憶體：`512 MB`
- Timeout：`30 秒`
- Handler：`main.handler`（Mangum handler 入口）
- 程式碼來源：`lambda/api/` 目錄（zip 封裝）
- 環境變數：
  - `JWT_SECRET_KEY`：JWT 簽署密鑰（部署時由 CDK Secrets Manager 或直接設定）
  - `JWT_EXPIRE_HOURS`：`24`
  - `USERS_TABLE`：`yt-to-mail-users`
  - `SUBSCRIPTIONS_TABLE`：`yt-to-mail-subscriptions`
  - `HISTORY_TABLE`：`yt-to-mail-history`
  - `ENVIRONMENT`：`production`
- Function URL：
  - AuthType：`NONE`（JWT 由應用層驗證）
  - CORS 設定：
    - AllowOrigins：`["*"]`（Phase 4 完成後改為 CloudFront 網域）
    - AllowMethods：`["GET", "POST", "PUT", "DELETE", "OPTIONS"]`
    - AllowHeaders：`["Content-Type", "Authorization"]`
    - MaxAge：`3600`

#### IAM Lambda 執行角色

- 角色名稱：`yt-to-mail-api-lambda-role`
- 信任政策：Lambda 服務
- 附加 Policy（最小權限）：
  - DynamoDB 操作：`dynamodb:GetItem`、`dynamodb:PutItem`、`dynamodb:UpdateItem`、`dynamodb:DeleteItem`、`dynamodb:Query`、`dynamodb:Scan`
  - 資源範圍：三張 DynamoDB 表及其 GSI（`arn:aws:dynamodb:<region>:<account>:table/yt-to-mail-*`）
  - CloudWatch Logs：`logs:CreateLogGroup`、`logs:CreateLogStream`、`logs:PutLogEvents`

---

### CDK Stack 結構

- Stack 名稱：`YtToMailBackendStack`
- 檔案位置：`lib/yt-to-mail-backend-stack.ts`
- Construct 層次：
  ```
  YtToMailBackendStack
  ├── DynamoDB Table: yt-to-mail-users
  │     └── GSI: email-index
  ├── DynamoDB Table: yt-to-mail-subscriptions
  │     └── GSI: user_id-index
  ├── DynamoDB Table: yt-to-mail-history
  │     └── GSI: user_id-index
  ├── IAM Role: yt-to-mail-api-lambda-role
  ├── Lambda Function: yt-to-mail-api
  │     └── FunctionUrl (NONE auth, CORS)
  └── CfnOutput: FunctionUrl（輸出給前端使用）
  ```

---

### Lambda 應用程式架構

**目錄結構**：
```
lambda/api/
  main.py              # Mangum handler 入口，FastAPI app 定義
  routers/
    auth.py            # /auth/register, /auth/login
    subscriptions.py   # /subscriptions CRUD
    history.py         # /history GET
    channels.py        # /channels/verify POST
  models/
    user.py            # Pydantic 模型：UserCreate, UserLogin, UserResponse
    subscription.py    # Pydantic 模型：SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse
    history.py         # Pydantic 模型：HistoryResponse
  services/
    auth_service.py    # JWT 產生與驗證、bcrypt 密碼處理
    dynamo_service.py  # DynamoDB 通用操作封裝
  dependencies.py      # FastAPI Depends：get_current_user
  requirements.txt
```

**必要套件（requirements.txt）**：
```
fastapi==0.115.0
mangum==0.19.0
pydantic==2.0.0
python-jose[cryptography]==3.3.0
bcrypt==4.0.1
boto3==1.34.0
```

---

### API 介面規格

所有需要認證的端點，Request Header 必須包含：
```
Authorization: Bearer <JWT token>
```

#### POST /auth/register — 用戶註冊

**Request Body**：
```json
{
  "email": "user@example.com",
  "password": "minimum8chars"
}
```

**驗證規則**：
- email：有效 Email 格式
- password：長度 ≥ 8 字元

**Response 201**：
```json
{
  "id": "uuid-v4",
  "email": "user@example.com",
  "created_at": "2026-05-01T00:00:00Z"
}
```

**錯誤碼**：
- `400`：缺少欄位或格式錯誤
- `409`：Email 已存在

---

#### POST /auth/login — 用戶登入

**Request Body**：
```json
{
  "email": "user@example.com",
  "password": "minimum8chars"
}
```

**Response 200**：
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**錯誤碼**：
- `401`：Email 不存在或密碼錯誤（統一回傳，不揭露哪個錯誤）

---

#### GET /subscriptions — 取得我的訂閱列表

**需要認證**：是

**Response 200**：
```json
[
  {
    "id": "uuid-v4",
    "channel_url": "https://www.youtube.com/@channel",
    "channel_id": "UCxxxxxxxxxx",
    "channel_name": "頻道名稱",
    "recipient_email": "recv@example.com",
    "audio_speed": 1.0,
    "send_time": "14:00",
    "is_active": true,
    "created_at": "2026-05-01T00:00:00Z"
  }
]
```

---

#### POST /subscriptions — 新增訂閱

**需要認證**：是

**Request Body**：
```json
{
  "channel_url": "https://www.youtube.com/@channel",
  "channel_id": "UCxxxxxxxxxx",
  "channel_name": "頻道名稱",
  "recipient_email": "recv@example.com",
  "audio_speed": 1.0,
  "send_time": "14:00"
}
```

**驗證規則**：
- 同一 user_id 的訂閱數量 ≤ 5，超過回傳 `400`
- `audio_speed` 必須為 0.5, 1.0, 1.5, 2.0 其中之一
- `send_time` 格式為 `HH:MM`（00:00 ～ 23:59）

**Response 201**：回傳建立後的完整訂閱物件（同 GET 格式）

**錯誤碼**：
- `400`：欄位驗證失敗或已達上限 5 個

---

#### PUT /subscriptions/{id} — 修改訂閱

**需要認證**：是

**路徑參數**：`id` — 訂閱 UUID

**Request Body**（所有欄位可選）：
```json
{
  "recipient_email": "new@example.com",
  "audio_speed": 1.5,
  "send_time": "09:00",
  "is_active": false
}
```

**Response 200**：回傳更新後的完整訂閱物件

**錯誤碼**：
- `403`：訂閱不屬於當前用戶
- `404`：訂閱不存在

---

#### DELETE /subscriptions/{id} — 刪除訂閱

**需要認證**：是

**路徑參數**：`id` — 訂閱 UUID

**Response 200**：
```json
{
  "message": "deleted"
}
```

**錯誤碼**：
- `403`：訂閱不屬於當前用戶
- `404`：訂閱不存在

---

#### GET /history — 取得歷史紀錄

**需要認證**：是

**Query 參數**：
- `limit`：整數，預設 20，最大 100
- `subscription_id`：可選，篩選特定訂閱

**Response 200**：
```json
[
  {
    "id": "uuid-v4",
    "subscription_id": "uuid-v4",
    "video_id": "dQw4w9WgXcQ",
    "video_title": "影片標題",
    "sent_at": "2026-05-01T14:00:00Z",
    "status": "done"
  }
]
```

---

#### POST /channels/verify — 頻道資訊確認

**需要認證**：是

**說明**：前端新增訂閱時，傳入頻道 URL 讓後端解析並回傳頻道資訊，供用戶確認後再正式建立訂閱。此端點不呼叫 YouTube API，僅做 URL 格式解析與正規化。

**Request Body**：
```json
{
  "channel_url": "https://www.youtube.com/@channelname"
}
```

**Response 200**：
```json
{
  "channel_url": "https://www.youtube.com/@channelname",
  "channel_id": "UCxxxxxxxxxx",
  "channel_name": "channelname"
}
```

**錯誤碼**：
- `400`：無效的 YouTube 頻道 URL 格式
- `422`：無法解析頻道資訊

**URL 解析邏輯**：
- 接受格式：`https://www.youtube.com/@handle`、`https://www.youtube.com/channel/UCxxx`
- channel_id：若為 `/channel/UCxxx` 格式直接提取；若為 `/@handle` 格式則 channel_id 暫填 handle，channel_name 填 handle（原型階段不呼叫 YouTube Data API）

---

### JWT 規格

- 演算法：`HS256`
- 過期時間：`24 小時`
- Payload：
  ```json
  {
    "sub": "<user_id>",
    "email": "<user_email>",
    "exp": <unix timestamp>,
    "iat": <unix timestamp>
  }
  ```
- Secret Key：從 Lambda 環境變數 `JWT_SECRET_KEY` 讀取，長度 ≥ 32 字元
- 驗證失敗時統一回傳 `401 Unauthorized`

---

### 環境變數

| 環境變數名稱 | 說明 | 範例值 |
|---|---|---|
| `JWT_SECRET_KEY` | JWT 簽署密鑰 | 隨機 32 字元以上字串 |
| `JWT_EXPIRE_HOURS` | JWT 過期小時數 | `24` |
| `USERS_TABLE` | DynamoDB users 表名稱 | `yt-to-mail-users` |
| `SUBSCRIPTIONS_TABLE` | DynamoDB subscriptions 表名稱 | `yt-to-mail-subscriptions` |
| `HISTORY_TABLE` | DynamoDB history 表名稱 | `yt-to-mail-history` |
| `ENVIRONMENT` | 環境識別 | `production` |

---

## 實作步驟（供 cdk-coder 執行）

- Step 1：建立 CDK Stack `YtToMailBackendStack`，定義三張 DynamoDB 資料表及 GSI
- Step 2：建立 IAM 執行角色，設定 DynamoDB 最小權限 Policy
- Step 3：建立 Lambda Function，掛載 IAM 角色，設定環境變數
- Step 4：啟用 Lambda Function URL，設定 CORS（AllowOrigins: `["*"]`）
- Step 5：建立 `lambda/api/` 目錄，撰寫 `requirements.txt`
- Step 6：實作 FastAPI 應用主體（`main.py`），以 Mangum 包裝
- Step 7：實作 `services/auth_service.py`（bcrypt 密碼處理、JWT 產生與驗證）
- Step 8：實作 `services/dynamo_service.py`（DynamoDB 通用 CRUD 封裝）
- Step 9：實作 `dependencies.py`（FastAPI Depends get_current_user）
- Step 10：實作 `routers/auth.py`（register / login）
- Step 11：實作 `routers/subscriptions.py`（GET / POST / PUT / DELETE，含 5 個上限驗證）
- Step 12：實作 `routers/history.py`（GET，含 limit / subscription_id 篩選）
- Step 13：實作 `routers/channels.py`（POST /channels/verify，URL 解析）
- Step 14：實作 Pydantic 模型（`models/` 目錄）
- Step 15：加入 CDK 部署前自動 pip install 到 Lambda 封裝目錄的 bundling 設定
- Step 16：輸出 Function URL（`CfnOutput`），供後續 Phase 使用

---

## 驗收標準

- [ ] `cdk synth` 無錯誤，產出三張 DynamoDB 表、Lambda Function、Function URL
- [ ] `POST /auth/register` 可建立用戶，密碼以 bcrypt 儲存於 DynamoDB
- [ ] `POST /auth/login` 回傳有效 JWT，過期時間 24 小時
- [ ] `GET /subscriptions` 需攜帶有效 JWT，否則回傳 401
- [ ] `POST /subscriptions` 新增第 6 個訂閱時回傳 400
- [ ] `PUT /subscriptions/{id}` 修改他人訂閱時回傳 403
- [ ] `DELETE /subscriptions/{id}` 刪除後資料從 DynamoDB 移除
- [ ] `GET /history` 依 user_id GSI 查詢，僅回傳當前用戶資料
- [ ] `POST /channels/verify` 正確解析 `@handle` 和 `/channel/UCxxx` 格式
- [ ] Lambda Function URL CORS 設定允許所有來源（`*`）
- [ ] Lambda 執行角色僅有 yt-to-mail-* 表的操作權限

---

## 注意事項與限制

- `JWT_SECRET_KEY` 不得寫死在程式碼中，必須從環境變數讀取
- bcrypt 雜湊 rounds 設 12，不得低於此值
- 所有 DynamoDB 操作使用 boto3 resource 模式（非 client 模式），程式碼較簡潔
- Lambda Function URL 的 CORS 設定在 Phase 4 完成後須改為 CloudFront 實際網域
- 原型階段 `/channels/verify` 不呼叫 YouTube Data API，僅做 URL 解析
- 禁止在 Lambda 程式碼中使用硬編碼 AWS region，使用 `boto3.resource('dynamodb')` 自動讀取環境
- 所有函式必須包含繁體中文函式級註解
