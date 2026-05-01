# yt-to-mail v2 開發計畫書

**版本**：2.0  
**日期**：2026-05-01  
**階段**：原型（≤ 20 用戶）

---

## 產品定義

**核心功能**：用戶指定 YouTube 短影音頻道，系統每天自動寄送文字稿與音訊到信箱。

**可客製化參數**：
- 收件人信箱
- 追蹤的 YouTube 頻道
- 音訊語速（0.5x～2.0x）
- 每日發送時間

**用戶功能**：帳號登入、訂閱管理、歷史紀錄

**影片篩選限制**：
- 時長 ≤ 60 秒（YouTube API `videoDuration=short` 初篩 + `videos.list` 取得實際時長二次過濾）
- 僅英文頻道（Whisper 轉錄後判斷 `language == "en"`，非英文自動跳過並記錄 `skipped_language`）
- 每人最多 5 個訂閱（Lambda API 新增訂閱時驗證）

---

## 原型架構（方案 B：AWS API + 本機處理器）

```
用戶瀏覽器
    │
    ▼
[CloudFront + S3]              ← 前端靜態網站（React）
    │ API 請求（HTTPS）
    ▼
[Lambda Function URL]          ← 後端 API（AWS 雲端，無需 API Gateway）
    │
    ▼
[DynamoDB]                     ← 用戶設定、訂閱、歷史紀錄
    ▲
    │ 定時拉取訂閱資料（outbound only，本機不對外暴露）
    │
[本機排程器]                   ← Windows 工作排程器
    │
    ├──→ [yt-dlp]              ← 下載音訊（家用 IP，不被封鎖）
    ├──→ [Whisper]             ← 語音轉文字
    └──→ [Gmail API]           ← 寄信，並將結果寫回 DynamoDB
```

**為何選方案 B？**
- 本機不需對外暴露，只有 outbound 連線，安全性更高
- 訂閱資料存在 DynamoDB，電腦重開機不影響資料
- 本機只負責「下載 → 轉錄 → 寄信」，職責單純
- 費用與原方案相同（≤ 20 用戶均在 AWS 免費額度內）

**為何用 Lambda Function URL 而非 API Gateway？**
- 原型不需要 API Gateway 的進階功能（路由、rate limiting、stage）
- Lambda Function URL 直接提供 HTTPS 端點，設定更簡單
- 費用更低：只計算 Lambda 執行時間，無 API Gateway 費用

---

## 技術選型

| 元件 | 技術 | 說明 |
|------|------|------|
| 前端 | React + TypeScript | S3 靜態部署 |
| CDN | CloudFront | 使用 CloudFront 預設域名，無需自訂域名 |
| 後端 API | AWS Lambda Function URL + Mangum + FastAPI | 單一 Lambda 內部路由，原型最簡架構 |
| 資料庫 | DynamoDB | 雲端，用戶、訂閱、歷史紀錄 |
| 認證 | JWT（Lambda 驗證） | Secret key 存放於 Lambda 環境變數，原型不需要 Cognito |
| 本機排程 | Windows 工作排程器 | 定時從 DynamoDB 拉取訂閱並執行 |
| YouTube 下載 | yt-dlp | 家用 IP，不被封鎖 |
| 語音轉文字 | openai-whisper | 本機模型 |
| 寄信 | Gmail API | 沿用 v1 |

---

## 資料模型（DynamoDB）

### users 表
| 欄位 | 說明 |
|------|------|
| id（PK） | UUID |
| email | 登入用信箱（GSI） |
| password_hash | bcrypt 雜湊 |
| created_at | 建立時間 |

### subscriptions 表
| 欄位 | 說明 |
|------|------|
| id（PK） | UUID |
| user_id（GSI） | 外鍵 |
| channel_url | YouTube 頻道 URL |
| channel_id | YouTube channel_id |
| recipient_email | 收件信箱 |
| audio_speed | 語速 0.5～2.0 |
| send_time | HH:MM，儲存為 UTC 時間（前端換算後送出） |
| is_active | 是否啟用 |

### history 表
| 欄位 | 說明 |
|------|------|
| id（PK） | UUID |
| user_id（GSI） | 外鍵 |
| subscription_id | 外鍵 |
| video_id | YouTube video ID |
| video_title | 影片標題 |
| sent_at | 寄送時間 |
| status | done / failed / skipped_language |

---

## 前端頁面規劃

| 頁面 | 功能 |
|------|------|
| 登入/註冊 | Email + 密碼 |
| 首頁（訂閱列表） | 查看、啟用/停用訂閱、最後寄送狀態 |
| 新增訂閱 | 頻道 URL（含頻道確認）、收件信箱、語速、發送時間 |
| 歷史紀錄 | 已寄出的影片清單 |

---

## API 設計（Lambda Function URL）

```
POST   /auth/register        註冊
POST   /auth/login           登入，回傳 JWT

GET    /subscriptions        取得我的訂閱列表
POST   /subscriptions        新增訂閱（驗證上限 5 個）
PUT    /subscriptions/{id}   修改訂閱
DELETE /subscriptions/{id}   刪除訂閱

GET    /history              取得歷史紀錄
```

**時區處理規則**：
- 前端顯示用戶本地時間（瀏覽器自動取得時區）
- 送出 API 前換算為 UTC，`send_time` 統一儲存 UTC
- 本機排程器比對時間時使用 UTC，避免時差錯誤

---

## 費用估算（原型，≤ 20 用戶）

| 項目 | 費用 |
|------|------|
| CloudFront + S3 | ~$1/月 |
| API Gateway | 免費額度內（前 12 個月 100 萬次/月） |
| Lambda | 免費額度內（100 萬次/月） |
| DynamoDB | 免費額度內（25GB + 25 RCU/WCU） |
| 本機執行（電腦已開著） | $0 |
| **合計** | **~$1/月** |

---

## 開發階段

### Phase 1：雲端後端（Lambda + DynamoDB）
- [ ] 建立 DynamoDB 資料表（users、subscriptions、history）
- [ ] 建立單一 FastAPI 應用（Mangum 封裝，部署為單一 Lambda）
- [ ] 認證路由（register / login / JWT，secret key 存 Lambda 環境變數）
- [ ] 訂閱 CRUD 路由（含上限 5 個驗證）
- [ ] 歷史紀錄路由
- [ ] 啟用 Lambda Function URL（CORS 設定允許 CloudFront 來源）

### Phase 2：本機排程整合
- [ ] 建立 IAM User，`aws configure` 設定本機憑證（DynamoDB 讀寫權限）
- [ ] 本機腳本：從 DynamoDB 讀取到達 send_time 的訂閱（UTC 比對）
- [ ] 整合 v1 執行邏輯（下載 → 轉錄 → 英文判斷 → 寄信）
- [ ] 執行結果寫回 DynamoDB history 表
- [ ] Windows 工作排程器每分鐘執行一次

### Phase 3：前端（React）
- [ ] 建立 React + TypeScript 專案（Vite）
- [ ] 登入/註冊頁面
- [ ] 訂閱管理頁面（列表、新增含頻道確認、編輯、刪除）
- [ ] 歷史紀錄頁面

### Phase 4：部署
- [ ] 建立 S3 bucket（前端靜態檔案）
- [ ] 設定 CloudFront distribution
- [ ] 前端 build 並上傳 S3
- [ ] 設定前端 API base URL 指向 API Gateway 網址

---

## 已知風險

| 風險 | 因應 |
|------|------|
| 電腦關機時處理停止 | 原型可接受，資料安全存在 DynamoDB |
| DynamoDB 讀取需要 AWS 憑證 | 建立 IAM User，執行 `aws configure` 設定本機憑證 |
| Lambda 冷啟動延遲 | 原型可接受，≤ 20 用戶請求量低 |
| send_time 時區換算錯誤 | 前端統一換算為 UTC 再送出，本機排程器統一用 UTC 比對 |
| JWT 自製較簡陋 | 原型可接受，正式版改 Cognito |

---

## 正式版升級路徑（未來）

當用戶超過 20 人或需要穩定性時：
- 本機排程器 → ECS Fargate 或 EventBridge + Lambda
- 認證：自製 JWT → Cognito
- 寄信：Gmail API → SES
- YouTube 下載：若 Fargate IP 被封鎖 → 住宅代理 IP 服務
