# admin-channels-step17

## 功能名稱

管理員頻道白名單 — CDK 基礎設施 + 後端 API

## 目標

將系統從「使用者自由輸入 YouTube 頻道 URL」改為「管理員維護可訂閱頻道清單，使用者從下拉選單選擇」。
此步驟負責：
1. 新增 `yt-to-mail-channels` DynamoDB 資料表與 CDK 定義
2. 在 `yt-to-mail-subscriptions` 補充 `channel_id-index` GSI
3. 實作後端管理員頻道 CRUD API（`/admin/channels`）
4. 實作後端公開頻道列表 API（`GET /public/channels`）
5. 新增 `gmail_sender.py` 的 `send_admin_removed_email` 函式
6. 刪除已廢棄的 `lambda/api/routers/channels.py` 及相關掛載

---

## 技術規格

### AWS 服務與資源

#### 新增：`yt-to-mail-channels` DynamoDB 資料表
- 資料表名稱：`yt-to-mail-channels`
- Partition Key：`channel_id`（STRING）
- 欄位（不在 CDK 定義，由應用層寫入）：
  - `channel_name`（String）
  - `channel_url`（String）
  - `created_at`（String，ISO 8601 UTC）
- BillingMode：`PAY_PER_REQUEST`
- RemovalPolicy：`RETAIN`
- 無 GSI（channel_id 即主鍵，直接以 GetItem 查詢）

#### 修改：`yt-to-mail-subscriptions` 新增 GSI
- GSI 名稱：`channel_id-index`
- Partition Key：`channel_id`（STRING）
- ProjectionType：`ALL`
- 用途：管理員刪除頻道時，以 channel_id 快速查詢所有相關訂閱

#### Lambda 環境變數新增
- `CHANNELS_TABLE`：`yt-to-mail-channels`

#### IAM 權限
現有 Lambda 執行角色（`yt-to-mail-api-lambda-role`）的 `dynamodb:*` 權限已使用萬用字元
`arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-*`，可自動涵蓋新資料表，**無需額外修改**。

---

### CDK Stack 結構

檔案：`yt-to-mail/lib/yt-to-mail-backend-stack.ts`

在 `Step 1` 區塊中，於 `historyTable` 之後新增 `channelsTable`：

```typescript
// channels 資料表：管理員維護的可訂閱頻道白名單
const channelsTable = new dynamodb.Table(this, 'ChannelsTable', {
  tableName: 'yt-to-mail-channels',
  partitionKey: {
    name: 'channel_id',
    type: dynamodb.AttributeType.STRING,
  },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
```

在 `subscriptionsTable` 的 GSI 定義之後，補充 `channel_id-index`：

```typescript
subscriptionsTable.addGlobalSecondaryIndex({
  indexName: 'channel_id-index',
  partitionKey: {
    name: 'channel_id',
    type: dynamodb.AttributeType.STRING,
  },
  projectionType: dynamodb.ProjectionType.ALL,
});
```

在 Lambda 環境變數中新增：

```typescript
CHANNELS_TABLE: 'yt-to-mail-channels',
```

新增 CfnOutput：

```typescript
new cdk.CfnOutput(this, 'ChannelsTableName', {
  value: channelsTable.tableName,
  description: 'DynamoDB channels 資料表名稱',
});
```

---

### API 介面

#### 管理員頻道 CRUD（需 admin JWT）

| Method | Path | 說明 |
|--------|------|------|
| `POST` | `/admin/channels` | 新增頻道 |
| `GET` | `/admin/channels` | 列出所有頻道 |
| `PATCH` | `/admin/channels/{channel_id}` | 更新頻道資訊 |
| `DELETE` | `/admin/channels/{channel_id}` | 刪除頻道（串聯取消訂閱） |

##### POST /admin/channels — Request Body
```json
{
  "channel_id": "string",
  "channel_name": "string",
  "channel_url": "string"
}
```

##### POST /admin/channels — Response 201
```json
{
  "channel_id": "string",
  "channel_name": "string",
  "channel_url": "string",
  "created_at": "2026-05-03T00:00:00Z"
}
```

- `channel_id` 重複時回傳 409

##### GET /admin/channels — Response 200
```json
[
  {
    "channel_id": "string",
    "channel_name": "string",
    "channel_url": "string",
    "created_at": "string"
  }
]
```

##### PATCH /admin/channels/{channel_id} — Request Body（所有欄位選填）
```json
{
  "channel_name": "string",
  "channel_url": "string"
}
```

- `channel_id` 不存在時回傳 404

##### DELETE /admin/channels/{channel_id} — Response 200
```json
{
  "message": "deleted",
  "cancelled_subscriptions": 3
}
```

串聯流程（在同一個請求中同步執行）：
1. 以 `channel_id-index` GSI 查詢所有訂閱此頻道的記錄
2. 對每筆訂閱的 `recipient_email` 呼叫 `send_admin_removed_email`
3. 批次刪除訂閱記錄（可逐一呼叫 `delete_item`，訂閱數量小規模可接受）
4. 刪除頻道記錄
5. 回傳被取消的訂閱數量

#### 公開頻道列表（無需認證）

| Method | Path | 說明 |
|--------|------|------|
| `GET` | `/public/channels` | 取得可訂閱頻道清單 |

##### GET /public/channels — Response 200
```json
[
  {
    "channel_id": "string",
    "channel_name": "string",
    "channel_url": "string"
  }
]
```

- 使用 `scan_table` 全表掃描（頻道數量小規模可接受）
- 不含 `created_at`（前端下拉選單不需此欄位）

---

### 資料模型

#### 新增 Pydantic 模型（`lambda/api/models/channel.py`）

```python
class ChannelCreate(BaseModel):
    channel_id: str          # YouTube handle 或 channel ID
    channel_name: str
    channel_url: str

class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None

class ChannelResponse(BaseModel):
    channel_id: str
    channel_name: str
    channel_url: str
    created_at: str

class PublicChannelResponse(BaseModel):
    channel_id: str
    channel_name: str
    channel_url: str
```

---

### 後端修改清單

#### 新增檔案

1. **`yt-to-mail/lambda/api/models/channel.py`**
   - 定義 `ChannelCreate`、`ChannelUpdate`、`ChannelResponse`、`PublicChannelResponse`

2. **`yt-to-mail/lambda/api/routers/admin_channels.py`**
   - Router prefix：掛載至 `/admin/channels`（在 `main.py` 設定 prefix）
   - 端點：`POST /`、`GET /`、`PATCH /{channel_id}`、`DELETE /{channel_id}`
   - 所有端點 Depends `get_current_admin`
   - `DELETE /{channel_id}` 串聯邏輯：
     1. 確認頻道存在（GetItem），不存在回傳 404
     2. `query_by_gsi_partition(SUBSCRIPTIONS_TABLE, "channel_id-index", "channel_id", channel_id)` 取得所有相關訂閱
     3. 對每筆訂閱呼叫 `send_admin_removed_email(recipient_email, channel_name, channel_url)`
     4. `delete_item` 逐一刪除訂閱
     5. `delete_item` 刪除頻道
     6. 回傳 `{"message": "deleted", "cancelled_subscriptions": len(subscriptions)}`

#### 修改現有檔案

3. **`yt-to-mail/lambda/api/routers/public.py`**
   - 新增 `GET /channels` 端點（函式名 `list_public_channels`）
   - 使用 `scan_table(CHANNELS_TABLE)` 取得所有頻道
   - 回傳 `list[PublicChannelResponse]`
   - 新增 `_CHANNELS_TABLE = os.environ.get("CHANNELS_TABLE", "yt-to-mail-channels")`

4. **`yt-to-mail/lambda/api/main.py`**
   - 移除 `channels` router 的 import 與 `app.include_router(channels.router, ...)` 這行
   - 新增 `from routers import admin_channels`
   - 新增 `app.include_router(admin_channels.router, prefix="/admin/channels", tags=["admin-channels"])`
   - 注意：`admin.router` 仍掛載於 `/admin`，`admin_channels.router` 掛載於 `/admin/channels`，兩者共存不衝突

5. **`yt-to-mail/scheduler/gmail_sender.py`**
   - 新增 `send_admin_removed_email(recipient_email, channel_name, channel_url)` 函式
   - 郵件主旨：`[yt-to-mail] 您對「{channel_name}」的訂閱已由管理員移除`
   - 內文說明：頻道已由系統管理員從可訂閱清單中移除，您的訂閱已自動取消
   - 不含重新訂閱連結（頻道已從白名單移除）
   - 結構與 `send_auto_cancel_email` 相同（MIMEMultipart("alternative")，純文字 + HTML）

#### 刪除檔案

6. **`yt-to-mail/lambda/api/routers/channels.py`**
   - 整個檔案刪除

#### 修改 CDK

7. **`yt-to-mail/lib/yt-to-mail-backend-stack.ts`**
   - 新增 `channelsTable`
   - 新增 `channel_id-index` GSI 至 `subscriptionsTable`
   - 新增 `CHANNELS_TABLE` 環境變數
   - 新增 `ChannelsTableName` CfnOutput

---

### dynamo_service.py 補充確認

現有 `query_by_gsi_partition` 函式已存在且可接受任意 table name、index name、partition key name/value，
可直接複用查詢 `channel_id-index`，**無需修改此檔案**。

---

### IAM 權限

Lambda 執行角色現有 Policy：
```
arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-*
```
新資料表 `yt-to-mail-channels` 自動包含在此範圍，無需額外授權。

但 `channel_id-index` GSI 查詢需要 `index/*` ARN，現有 Policy 僅允許 table 層級。
確認現有 Policy 的 resources 列表：

```
arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-*
```

此 Wildcard 包含 `yt-to-mail-subscriptions` 但**不包含** `yt-to-mail-subscriptions/index/*`。
需在 CDK Policy 中補充 `/index/*` 資源：

```typescript
`arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-*/index/*`,
```

---

### 環境變數

| 變數名稱 | 值 | 說明 |
|---------|-----|------|
| `CHANNELS_TABLE` | `yt-to-mail-channels` | 頻道白名單資料表名稱 |

---

## 驗收條件

### CDK / 基礎設施
- [ ] `cdk synth` 通過，無 TypeScript 編譯錯誤
- [ ] `yt-to-mail-channels` 資料表在 CloudFormation template 中定義，PK 為 `channel_id`
- [ ] `yt-to-mail-subscriptions` 在 CloudFormation template 中含 `channel_id-index` GSI
- [ ] Lambda 環境變數含 `CHANNELS_TABLE: yt-to-mail-channels`
- [ ] Lambda IAM Policy resources 含 `table/yt-to-mail-*/index/*`

### 後端 API — 管理員頻道 CRUD
- [ ] `POST /admin/channels`（admin JWT）成功新增頻道，回傳 201 + ChannelResponse
- [ ] `POST /admin/channels` 重複 channel_id 回傳 409
- [ ] `POST /admin/channels` 無 admin JWT 回傳 403
- [ ] `GET /admin/channels`（admin JWT）回傳所有頻道列表
- [ ] `PATCH /admin/channels/{channel_id}`（admin JWT）成功更新，回傳 200 + ChannelResponse
- [ ] `PATCH /admin/channels/{channel_id}` 不存在時回傳 404
- [ ] `DELETE /admin/channels/{channel_id}` 存在 N 筆訂閱時，回傳 `cancelled_subscriptions: N`
- [ ] `DELETE /admin/channels/{channel_id}` 串聯寄出取消通知信（每筆訂閱一封）
- [ ] `DELETE /admin/channels/{channel_id}` 成功後訂閱記錄從 DynamoDB 刪除
- [ ] `DELETE /admin/channels/{channel_id}` 成功後頻道記錄從 DynamoDB 刪除

### 後端 API — 公開頻道列表
- [ ] `GET /public/channels`（無 JWT）回傳頻道清單（含 channel_id、channel_name、channel_url）
- [ ] 回傳格式為 JSON array，不含 created_at

### gmail_sender.py
- [ ] `send_admin_removed_email` 寄出郵件，主旨含「管理員移除」語意
- [ ] 郵件包含純文字與 HTML 雙版本
- [ ] 函式具備繁體中文函式級註解

### 刪除驗證
- [ ] `lambda/api/routers/channels.py` 不存在
- [ ] `main.py` 中不再 import `channels` router
- [ ] `GET /channels/verify` 端點不再回應（或回傳 404）

### 程式品質
- [ ] `tsc --noEmit` 通過
- [ ] 所有新增 Python 函式具備繁體中文函式級註解
- [ ] Python type hints 正確標注，無 `Any` 型別

---

## 工作分派（單 Coder 執行）

本 step 所有任務存在依賴關係，建議單一 cdk-coder 依序執行：

| 優先順序 | 負責檔案 | 任務描述 |
|---------|---------|---------|
| 1 | `yt-to-mail/lib/yt-to-mail-backend-stack.ts` | 新增 channelsTable、channel_id-index GSI、CHANNELS_TABLE 環境變數、index/* IAM Policy |
| 2 | `yt-to-mail/lambda/api/models/channel.py` | 新增 Pydantic Channel 模型 |
| 3 | `yt-to-mail/lambda/api/routers/admin_channels.py` | 實作管理員頻道 CRUD router |
| 4 | `yt-to-mail/lambda/api/routers/public.py` | 新增 GET /channels 端點 |
| 5 | `yt-to-mail/lambda/api/main.py` | 移除 channels router，掛載 admin_channels router |
| 6 | `yt-to-mail/scheduler/gmail_sender.py` | 新增 send_admin_removed_email |
| 7 | `yt-to-mail/lambda/api/routers/channels.py` | 刪除整個檔案 |

### 依賴順序
- 步驟 1（CDK）可先執行，不依賴其他步驟
- 步驟 2（models）必須在步驟 3（admin_channels router）之前完成
- 步驟 3 完成後才能執行步驟 5（main.py 掛載）
- 步驟 4（public.py）與步驟 3 平行，依賴步驟 2
- 步驟 6（gmail_sender）完全獨立，可最先或最後執行
- 步驟 7（刪除 channels.py）必須在步驟 5（main.py 更新 import）之後執行

---

## 開發階段拆分

- Step 17-A：CDK 基礎設施（`lib/yt-to-mail-backend-stack.ts`）
- Step 17-B：Pydantic models（`lambda/api/models/channel.py`）
- Step 17-C：管理員頻道 router（`lambda/api/routers/admin_channels.py`）
- Step 17-D：公開頻道端點（`lambda/api/routers/public.py` 新增 GET /channels）
- Step 17-E：主程式更新與刪除廢棄檔案（`main.py` 修改、`routers/channels.py` 刪除）
- Step 17-F：郵件通知（`scheduler/gmail_sender.py`）

---

## 注意事項與限制

1. **`frontend/src/api/channels.ts` 不在本 step 刪除**：此為前端任務，由 step18 處理。
2. **`public.py` 中現有的 `_parse_channel_url` 函式**：此函式目前複用 channels.py 的邏輯，channels.py 刪除後，`_parse_channel_url` 成為 public.py 的私有函式，不影響功能。但 `POST /public/subscribe` 依然會使用此函式解析 channel_url（此行為在新架構下仍需保留，因為後端 subscribe 仍需從 channel_url 推導 channel_id/channel_name）。
3. **後端 public.py 的 subscribe 邏輯不變**：`POST /public/subscribe` 仍接受 `channel_url` 並自行解析，前端改為下拉選單後，傳入的 channel_url 將來自 `GET /public/channels` 的回傳值，後端無需感知此差異。
4. **刪除 channels.py 前必須先更新 main.py**：否則會導致 import 失敗。
5. **`channel_id-index` GSI 新增為破壞性變更**：若現有 subscriptions 資料表已部署，此 GSI 在 `cdk deploy` 時會自動新增，現有資料不受影響（DynamoDB GSI 可在線新增）。
6. **DELETE /admin/channels 的通知信**：直接在 router 中 import `send_admin_removed_email` 並呼叫。不引入非同步佇列，因為訂閱數量小規模，Lambda timeout 30 秒足夠處理。
