# yt-to-mail v3 優化計畫書

**版本**：3.0  
**日期**：2026-05-03  
**階段**：原型優化（無帳號訂閱模式）  
**前提**：不改動主要架構與資料表 Key Schema / GSI，僅新增 DynamoDB item 欄位與 API endpoint

---

## 優化目標

v2 要求用戶先註冊帳號才能訂閱，測試階段門檻過高。  
v3 改為「**無帳號訂閱模式**」——用戶以 email 作為身份識別，直接完成訂閱與管理，  
同時保留管理員後台與自動取消機制，並預留未來恢復帳號系統的升級路徑。

---

## 變更項目一覽

| # | 項目 | 類型 | 影響範圍 |
|---|------|------|---------|
| 1 | 公開訂閱頁（無需登入） | 新增 | 前端、後端 API |
| 2 | Email 查詢頁（查訂閱、可取消） | 新增 | 前端、後端 API |
| 3 | 管理員後台 | 新增 | 前端、後端 API、環境變數 |
| 4 | 自動取消訂閱計數器 | 新增 | subscriptions 欄位、排程器、Gmail |

---

## 項目 1：公開訂閱頁（無需登入）

### 需求描述
用戶在訂閱頁輸入 email、頻道網址、語速，直接完成訂閱，不需要註冊帳號。

### 前端變更
- 移除 `AddSubscriptionPage` 的 `ProtectedRoute` 包裝
- 表單欄位：`recipient_email`、`channel_url`、`audio_speed`、`send_time`
- 表單送出後顯示成功訊息（不跳轉至訂閱管理頁）
- 根路由 `/` 導向訂閱頁

### 後端變更
- 新增公開 endpoint（無 JWT 驗證）：
  ```
  POST /public/subscribe
  ```
- Request body：`recipient_email`、`channel_url`、`audio_speed`、`send_time`
- `user_id` 直接使用 `recipient_email`（不查 users 表）
- 沿用現有訂閱上限（每個 email 最多 5 個訂閱）

### 資料模型
無需改動 subscriptions 表 Key Schema，`user_id` 欄位改存 email 字串即可。

---

## 項目 2：Email 查詢頁（查訂閱、可取消）

### 需求描述
用戶在查詢頁輸入 email，查看自己的訂閱紀錄，並可取消單筆訂閱。

### 前端變更
- 新增公開頁面 `/my-subscriptions`
- 輸入 email → 呼叫 API → 顯示訂閱清單
- 每筆訂閱顯示：頻道名稱、發送時間、語速、建立時間
- 提供「取消訂閱」按鈕，確認後呼叫刪除 API

### 後端變更
- 新增公開 endpoints（無 JWT 驗證）：
  ```
  GET    /public/subscriptions?email=xxx
  DELETE /public/subscriptions/{id}?email=xxx
  ```
- `GET`：利用現有 `user_id-index` GSI，以 `user_id = email` 查詢，O(訂閱數) 效率
- `DELETE`：後端驗證 `subscription.user_id == email`，防止他人刪除別人的訂閱

---

## 項目 3：管理員後台

### 需求描述
管理員以帳號密碼登入系統，查看所有用戶的訂閱列表，並可取消任意訂閱。

### 實作方式
**不新增資料表**，管理員帳密存於 Lambda 環境變數：
- `ADMIN_EMAIL`：管理員登入信箱
- `ADMIN_PASSWORD_HASH`：bcrypt 雜湊密碼

### 後端變更
- `POST /auth/login` 現有邏輯保留，加入 admin 判斷：
  - 若登入 email == `ADMIN_EMAIL` → JWT payload 加入 `is_admin: true`
- 新增 admin 專用 endpoints（需要 admin JWT）：
  ```
  GET    /admin/subscriptions          查詢全部訂閱（含用戶 email）
  DELETE /admin/subscriptions/{id}     取消任意訂閱
  ```
- `GET /admin/subscriptions`：Scan subscriptions 全表，回傳所有訂閱

### 前端變更
- 新增 `/admin/login` 頁面（獨立，不混入用戶流程）
- 新增 `/admin/subscriptions` 頁面（需要 admin JWT）
  - 欄位：用戶 email、頻道名稱、發送時間、語速、建立時間、操作（取消）
  - 支援依 email 篩選

### 安全考量
- admin JWT 有效期沿用現有設定（24 小時）
- 一般用戶 JWT 的 `is_admin` 為 false，無法存取 `/admin/*`
- 管理員密碼以 bcrypt 雜湊存於環境變數，不硬編碼

---

## 項目 4：自動取消訂閱計數器

### 需求描述
當頻道持續 N 天無新影片時，系統自動取消訂閱並寄通知信。  
N 由用戶在訂閱時自訂，**預設值 3 天**。

### 資料模型變更
在 subscriptions table 新增兩個欄位（DynamoDB schema-less，不改 Key Schema）：

| 欄位 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| `auto_cancel_days` | Number | 幾天無新影片後自動取消 | 3 |
| `no_new_video_days` | Number | 目前連續無新影片天數（系統維護） | 0 |

### 前端變更
- 訂閱表單新增 `auto_cancel_days` 欄位（數字輸入，min=1，預設 3）
- 查詢頁顯示「連續無新影片：N 天 / 設定上限：M 天」

### 後端變更
- `POST /public/subscribe` 接受並儲存 `auto_cancel_days`

### 排程器變更（processor.py）

**當有新影片寄出成功（status = done）：**
```python
# 重設計數器
subscriptions_table.update_item(
    Key={"id": subscription_id},
    UpdateExpression="SET no_new_video_days = :zero",
    ExpressionAttributeValues={":zero": 0},
)
```

**當候選清單均已寄過（skipped_duplicate）：**
```python
# 計數器 +1
response = subscriptions_table.update_item(
    Key={"id": subscription_id},
    UpdateExpression="SET no_new_video_days = no_new_video_days + :one",
    ExpressionAttributeValues={":one": 1},
    ReturnValues="UPDATED_NEW",
)
new_count = response["Attributes"]["no_new_video_days"]

if new_count >= auto_cancel_days:
    # 刪除訂閱
    subscriptions_table.delete_item(Key={"id": subscription_id})
    # 寄取消通知信
    gmail_sender.send_auto_cancel_email(
        recipient_email=recipient_email,
        channel_name=channel_name,
        auto_cancel_days=auto_cancel_days,
    )
    return {"status": "auto_cancelled", ...}
```

### Gmail 新增郵件模板
- `send_auto_cancel_email()`：通知用戶訂閱已因 N 天無新影片自動取消，並提供重新訂閱連結

---

## API 總覽（v3 新增）

```
# 公開端點（無需 JWT）
POST   /public/subscribe                    新增訂閱
GET    /public/subscriptions?email=xxx      查詢我的訂閱
DELETE /public/subscriptions/{id}?email=xxx 取消訂閱（需驗證 email）

# 管理員端點（需 admin JWT）
GET    /admin/subscriptions                 查詢全部訂閱
DELETE /admin/subscriptions/{id}            取消任意訂閱
```

v2 原有端點（`/auth/*`、`/subscriptions/*`、`/history/*`）**保留不動**。

---

## 未來恢復帳號系統的升級路徑

v3 以 email 作為 `user_id`，未來若需恢復帳號系統（用戶自行管理密碼、多裝置登入等），升級步驟如下：

### 步驟 1：前端（1 天）
- 恢復 `/login`、`/register` 頁面的連結入口
- 訂閱頁改回 ProtectedRoute，登入後自動填入 email

### 步驟 2：後端（半天）
- 恢復 `POST /subscriptions`（需 JWT）作為主要訂閱 endpoint
- 公開 endpoint 可保留給訪客試用，或直接下線

### 步驟 3：資料遷移（半天）
針對 v3 時期建立的訂閱（`user_id = email`），執行一次性遷移腳本：

```python
# 偽代碼
for sub in scan_subscriptions_where_user_id_is_email():
    user = find_user_by_email(sub["user_id"])
    if user:
        update_subscription_user_id(sub["id"], user["id"])
    # 若用戶不存在（訪客訂閱），可選擇保留 email 或建立帳號並通知
```

### 遷移風險
- v3 訂閱的 `user_id` 是 email 字串，v2 原始訂閱是 UUID，同一張表中混存
- 遷移腳本需逐筆處理，建議在排程器停機時執行
- 無帳號的訂閱者收到通知信邀請建立帳號，可選擇不建立帳號（訂閱繼續以 email 識別）

---

## 開發工作量估算

| 項目 | 前端 | 後端 | 排程器 | 合計 |
|------|------|------|--------|------|
| 1. 公開訂閱頁 | 1h | 1h | — | 2h |
| 2. Email 查詢頁 | 2h | 1h | — | 3h |
| 3. 管理員後台 | 3h | 2h | — | 5h |
| 4. 自動取消計數器 | 1h | 0.5h | 2h | 3.5h |
| **合計** | **7h** | **4.5h** | **2h** | **13.5h** |

---

## 已知風險

| 風險 | 因應 |
|------|------|
| 任何人知道他人 email 即可查詢其訂閱 | 原型可接受；未來可加驗證碼或 magic link |
| 管理員 env var 若洩漏，攻擊者可登入後台 | 定期輪換密碼；Lambda 環境變數不對外公開 |
| v3 與 v2 訂閱 `user_id` 格式混存 | 遷移腳本處理；或 v3 上線前清空舊資料 |
| 自動取消計數器若排程器當天未執行，計數不增加 | 原型可接受；正式版可改用 DynamoDB TTL 機制 |
