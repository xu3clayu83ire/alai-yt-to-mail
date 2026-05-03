# DailyCast 英文語音訂閱服務

YouTube 短影音自動摘要寄信服務。
使用者透過網頁前端訂閱 YouTube 頻道，本機排程器定期抓取YouTube最新短影音（≤ 60 秒），以 Whisper 語音轉文字後，將逐字稿與音訊附件寄送至指定信箱。

v3 起支援**無帳號訂閱模式**：使用者不需要註冊帳號，直接在首頁輸入 email 即可訂閱頻道；可在「我的訂閱」頁面以 email 查詢並管理訂閱。當頻道連續 N 天無新影片時，排程器會自動取消訂閱並寄送通知信。

## 線上展示

| 環境 | URL |
|------|-----|
| dev | https://drtl6k13ydgdp.cloudfront.net/ |

---

## 系統架構

```
使用者瀏覽器
    │
    │  HTTPS（React SPA）
    ▼
CloudFront Distribution
    │
    │  OAC (SigV4)
    ▼
S3 Bucket（靜態前端資源）

    +───────────────────────────────────────+
    │                                       │
    │  HTTPS API 呼叫（axios）              │
    ▼                                       │
Lambda Function URL（AuthType NONE）        │
    │                                       │
    │  FastAPI + Mangum                     │
    ├── /public/*（無需登入）               │
    ├── /auth/*（JWT 簽發）                 │
    ├── /subscriptions（JWT 必要）          │
    ├── /admin/*（admin JWT 必要）          │
    ▼                                       │
DynamoDB                                    │
  ├── yt-to-mail-users（帳號、密碼雜湊）   │
  ├── yt-to-mail-subscriptions（訂閱設定） │◄──── 本機排程器（Windows）
  └── yt-to-mail-history（寄信歷史）       │    yt-dlp + Whisper + Gmail API
                                            │    自動取消計數器（dynamo_updater）
    +───────────────────────────────────────+
```

### 資料流說明

| 流程 | 路徑 |
|------|------|
| 前端靜態檔案 | 瀏覽器 → CloudFront → S3（OAC SigV4 保護） |
| API 請求 | 瀏覽器 → Lambda Function URL → FastAPI → DynamoDB |
| 排程任務 | 本機排程器 → DynamoDB（讀訂閱、寫歷史）→ Gmail |

---

## 技術棧

### 前端
| 技術 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| Vite | 8 | 建置工具 |
| TypeScript | 6 | 型別安全 |
| TanStack Query | 5 | 伺服器狀態管理與快取 |
| React Router | 7 | 客戶端路由 |
| Tailwind CSS | 4 | 樣式 |
| React Hook Form + Zod | 7 / 4 | 表單驗證 |
| axios | 1 | HTTP 用戶端 |

### 後端（Lambda）
| 技術 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | Runtime |
| FastAPI | 0.115 | Web 框架 |
| Mangum | 0.19 | Lambda 適配器 |
| python-jose | 3.3 | JWT 簽發與驗證 |
| bcrypt | 4.1 | 密碼雜湊 |
| pydantic | 2.9 | 資料驗證 |
| boto3 | 1.34 | AWS SDK（DynamoDB） |

### 本機排程器
| 技術 | 用途 |
|------|------|
| yt-dlp | 下載 YouTube 音訊 |
| Whisper | 語音轉文字（本機推論） |
| Gmail API（OAuth2） | 寄送逐字稿信件 |
| Windows 工作排程器 | 每分鐘觸發排程 |

### 基礎設施
| 技術 | 版本 | 用途 |
|------|------|------|
| AWS CDK（TypeScript） | 2.252.0 | 基礎設施即程式碼 |
| Amazon DynamoDB | — | 無伺服器資料庫（PAY_PER_REQUEST） |
| AWS Lambda | — | 無伺服器 API 執行環境 |
| Lambda Function URL | — | 取代 API Gateway，降低成本 |
| Amazon CloudFront | — | CDN + HTTPS 終端 |
| Amazon S3 | — | 靜態網站托管 |

---

## 專案目錄結構

```
yt-to-mail/
  bin/
    yt-to-mail.ts         # CDK 應用程式入口，掛載兩個 Stack
  lib/
    yt-to-mail-backend-stack.ts   # DynamoDB + Lambda + IAM
    yt-to-mail-frontend-stack.ts  # S3 + CloudFront + OAC
  lambda/
    api/
      main.py             # FastAPI 應用入口（Mangum handler）
      requirements.txt    # Python 依賴清單
      routers/            # 路由模組（auth / subscriptions / history / channels / public / admin）
      models/             # Pydantic 資料模型
      services/           # 業務邏輯層
      dependencies.py     # JWT 依賴（get_current_user / get_current_admin）
  frontend/
    src/
      pages/              # 頁面元件（含 AdminLoginPage / AdminSubscriptionsPage / PublicSubscriptionListPage）
      api/                # API 呼叫模組（auth / subscriptions / public / admin）
      components/         # 共用元件（含 AdminRoute 守衛）
      utils/              # 工具函式（timezone / storage）
      types/              # TypeScript 型別定義
    public/               # 靜態資源
    index.html            # SPA 入口
    vite.config.ts        # Vite 設定
    .env.example          # 前端環境變數範本
    .env.production       # 生產環境 API URL（不含密鑰，可納入版控）
  scheduler/
    run.py                # 排程器主程式
    processor.py          # 影片處理 + 自動取消計數器邏輯
    dynamo_updater.py     # DynamoDB 計數器原子操作（v3 新增）
    gmail_sender.py       # Gmail 寄信（含自動取消通知信）
    dynamo_reader.py      # 讀取訂閱資料
    history_writer.py     # 寫入寄信歷史
    config.py             # 環境變數管理（含 FRONTEND_URL）
    .env.example          # 排程器環境變數範本
    README.md             # 排程器完整說明文件
  test/                   # CDK Stack 單元測試（Jest）
  feature/                # 開發規格與進度文件
  .env.example            # 根目錄環境變數範本（舊版單機模式）
  cdk.json                # CDK 設定
  package.json            # CDK 相依套件
  tsconfig.json           # TypeScript 設定
```

---

## 前置需求

| 工具 | 版本 | 說明 |
|------|------|------|
| Node.js | 18 以上 | CDK CLI 與前端建置所需 |
| AWS CLI | 2.x | 部署與上傳靜態檔案 |
| AWS CDK | 2.1120.0 | `npm install -g aws-cdk` |
| Python | 3.12 | 本機排程器 |
| FFmpeg | 最新版 | 排程器音訊處理，需加入 PATH |
| Docker | 最新版 | CDK Lambda 打包時所需（bundling 使用容器） |

---

## 快速開始

### 1. 安裝 CDK 相依套件

```powershell
cd d:\12_Claude_Assistant\yt-to-mail
npm install
```

### 2. Bootstrap AWS 環境（首次使用）

```powershell
cdk bootstrap
```

### 3. 首次部署（CORS 允許所有來源）

```powershell
cdk deploy --all
```

若要在部署時設定管理員帳號與前端網址（v3 新增），可加入 CDK Context 參數：

```powershell
cdk deploy --all `
  --context adminEmail=admin@example.com `
  --context adminPasswordHash='$2b$12$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' `
  --context frontendUrl=https://<CloudFrontDomain>
```

> `adminPasswordHash` 請使用 bcrypt 工具預先產生，例如：
> ```python
> import bcrypt
> print(bcrypt.hashpw(b"your-password", bcrypt.gensalt()).decode())
> ```

部署完成後，終端機輸出會顯示：

- `YtToMailBackendStack.ApiEndpoint` — Lambda Function URL
- `YtToMailFrontendStack.CloudFrontDomain` — CloudFront 網域名稱（不含 https://）
- `YtToMailFrontendStack.S3BucketName` — S3 Bucket 名稱
- `YtToMailFrontendStack.CloudFrontDistributionId` — Distribution ID
- `YtToMailBackendStack.SchedulerAccessKeyId` — 排程器 IAM Access Key ID
- `YtToMailBackendStack.SchedulerSecretAccessKey` — 排程器 IAM Secret Key（請立即妥善保存）

### 4. 設定 Lambda 環境變數

部署完成後，至 AWS Lambda 主控台設定 `JWT_SECRET_KEY`（見下方環境變數說明）。

### 5. 建置並上傳前端

```powershell
cd d:\12_Claude_Assistant\yt-to-mail\frontend

# 將 Lambda Function URL 寫入生產環境設定
# 編輯 .env.production，填入步驟 3 取得的 ApiEndpoint
# VITE_API_BASE_URL=https://<your-lambda-url>.lambda-url.<region>.on.aws

npm install
npm run build

# 上傳靜態檔案至 S3（替換 <S3BucketName> 與 <CloudFrontDistributionId>）
aws s3 sync dist/ s3://<S3BucketName> --delete
aws cloudfront create-invalidation --distribution-id <CloudFrontDistributionId> --paths "/*"
```

### 6. 限縮 CORS（第二次部署）

取得 CloudFront 網域後，重新部署 Backend Stack 將 CORS 限縮至該網域，同時設定管理員帳號與前端網址：

```powershell
cd d:\12_Claude_Assistant\yt-to-mail

cdk deploy YtToMailBackendStack `
  --context allowedOrigin=https://<CloudFrontDomain> `
  --context adminEmail=admin@example.com `
  --context adminPasswordHash='$2b$12$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' `
  --context frontendUrl=https://<CloudFrontDomain>
```

此步驟完成後，Lambda Function URL 只接受來自 CloudFront 網域的跨域請求。

---

## 環境變數說明

### Lambda 環境變數（後端）

| 變數名稱 | 必填 | 說明 | 範例值 |
|----------|------|------|--------|
| `JWT_SECRET_KEY` | 是 | JWT 簽署密鑰，部署後手動設定 | `your-secret-key-32-chars` |
| `JWT_EXPIRE_HOURS` | 否 | JWT 有效時數，預設 24 | `24` |
| `USERS_TABLE` | 是 | DynamoDB users 表名稱 | `yt-to-mail-users` |
| `SUBSCRIPTIONS_TABLE` | 是 | DynamoDB subscriptions 表名稱 | `yt-to-mail-subscriptions` |
| `HISTORY_TABLE` | 是 | DynamoDB history 表名稱 | `yt-to-mail-history` |
| `ADMIN_EMAIL` | 否 | 管理員 email，由 CDK Context `adminEmail` 注入 | `admin@example.com` |
| `ADMIN_PASSWORD_HASH` | 否 | 管理員密碼 bcrypt 雜湊，由 CDK Context `adminPasswordHash` 注入 | `$2b$12$xxx...` |
| `ENVIRONMENT` | 否 | 執行環境標記 | `production` |

> `JWT_SECRET_KEY` 預設為空字串，**未設定時 JWT 功能無法使用**。建議至少使用 32 字元的隨機字串，或改用 AWS Secrets Manager 注入。  
> `ADMIN_EMAIL` 與 `ADMIN_PASSWORD_HASH` 未設定時，管理員登入功能不啟用，一般用戶登入不受影響。

### 前端環境變數（Vite）

| 變數名稱 | 必填 | 說明 | 範例值 |
|----------|------|------|--------|
| `VITE_API_BASE_URL` | 是 | Lambda Function URL（不含尾斜線） | `https://xxx.lambda-url.us-east-1.on.aws` |

設定檔位置：`frontend/.env.production`（生產建置）或 `frontend/.env`（本機開發）。

### 排程器環境變數（本機）

| 變數名稱 | 必填 | 說明 | 範例值 |
|----------|------|------|--------|
| `AWS_REGION` | 是 | DynamoDB 所在 Region | `ap-northeast-1` |
| `SUBSCRIPTIONS_TABLE` | 是 | DynamoDB subscriptions 表名稱 | `yt-to-mail-subscriptions` |
| `HISTORY_TABLE` | 是 | DynamoDB history 表名稱 | `yt-to-mail-history` |
| `GMAIL_CREDENTIALS_FILE` | 是 | Gmail OAuth2 credentials.json 絕對路徑 | `C:\path\to\credentials.json` |
| `GMAIL_TOKEN_FILE` | 是 | Gmail token.json 絕對路徑 | `C:\path\to\token.json` |
| `GMAIL_SENDER` | 是 | 寄件人 Gmail 地址 | `your@gmail.com` |
| `FRONTEND_URL` | 是 | 前端網址，用於自動取消通知信中的重新訂閱連結 | `https://drtl6k13ydgdp.cloudfront.net` |
| `WHISPER_MODEL` | 否 | Whisper 模型大小，預設 base | `base` |
| `YTDLP_OUTPUT_DIR` | 否 | yt-dlp 暫存目錄 | `C:\temp\yt-to-mail` |

詳細設定步驟請參閱 `scheduler/README.md`。

---

## 本機開發說明

### 前端本機開發

```powershell
cd d:\12_Claude_Assistant\yt-to-mail\frontend

# 複製環境變數範本
Copy-Item .env.example .env

# 編輯 .env，填入 Lambda Function URL
# VITE_API_BASE_URL=https://<your-lambda-url>.lambda-url.<region>.on.aws

npm install
npm run dev
# 瀏覽器開啟 http://localhost:5173
```

### 後端本機執行（FastAPI）

```powershell
cd d:\12_Claude_Assistant\yt-to-mail\lambda\api

# 建立並啟用虛擬環境
python -m venv .venv
.venv\Scripts\Activate.ps1

# 安裝相依套件
pip install -r requirements.txt

# 複製並設定環境變數
Copy-Item .env.example .env
# 編輯 .env 填入 JWT_SECRET_KEY 與 DynamoDB 設定

# 啟動開發伺服器
uvicorn main:app --reload --port 8000
# API 文件：http://localhost:8000/docs
```

本機執行時需設定 AWS 憑證（`aws configure`），確保能存取 DynamoDB。

### CDK 測試

```powershell
cd d:\12_Claude_Assistant\yt-to-mail
npm test
```

---

## DynamoDB 資料表設計

| 資料表 | Partition Key | GSI | 用途 |
|--------|---------------|-----|------|
| `yt-to-mail-users` | `id` (String) | `email-index`（PK: email） | 帳號與密碼雜湊 |
| `yt-to-mail-subscriptions` | `id` (String) | `user_id-index`（PK: user_id） | 頻道訂閱設定（含 `auto_cancel_days`、`no_new_video_days`） |
| `yt-to-mail-history` | `id` (String) | `user_id-index`（PK: user_id, SK: sent_at） | 寄信執行歷史 |

所有資料表採用 `PAY_PER_REQUEST` 計費模式，`RemovalPolicy.RETAIN` 防止誤刪。

> v3 起，`yt-to-mail-subscriptions` 新增兩個欄位：
> - `auto_cancel_days`：連續無新影片幾天後自動取消訂閱，預設 3。
> - `no_new_video_days`：排程器累計的連續無新影片天數，由排程器以原子 ADD 操作更新。

---

## API 路由概覽

### 公開端點（無需認證）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/health` | 健康檢查 |
| POST | `/auth/register` | 用戶註冊 |
| POST | `/auth/login` | 用戶登入，回傳 JWT（管理員登入時 payload 含 `is_admin: true`） |
| POST | `/public/subscribe` | 無帳號直接訂閱頻道，需傳入 `recipient_email` |
| GET | `/public/subscriptions?email=xxx` | 以 email 查詢訂閱清單 |
| DELETE | `/public/subscriptions/{id}?email=xxx` | 以 email 驗證後取消訂閱 |
| GET | `/channels/validate` | 驗證 YouTube 頻道 URL |

### 一般用戶端點（需 JWT）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/subscriptions` | 取得當前用戶所有訂閱 |
| POST | `/subscriptions` | 新增訂閱 |
| PUT | `/subscriptions/{id}` | 更新訂閱 |
| DELETE | `/subscriptions/{id}` | 刪除訂閱 |
| GET | `/history` | 取得寄信歷史 |

### 管理員端點（需 admin JWT）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/admin/subscriptions` | 取得全表訂閱，支援 `?email=xxx` 篩選 |
| DELETE | `/admin/subscriptions/{id}` | 刪除任意訂閱 |

互動式 API 文件（本機）：`http://localhost:8000/docs`

---

## 前端路由說明

React SPA 採用 React Router v7，路由守衛分為三種：**公開路由**、**一般用戶保護路由**、**管理員路由**。

### 路由一覽

| 路徑 | 頁面元件 | 守衛類型 | 說明 |
|------|----------|----------|------|
| `/` | `AddSubscriptionPage` | 公開 | 訂閱頻道（無需帳號），為首頁 |
| `/subscriptions/add` | `AddSubscriptionPage` | 公開 | 同 `/`，為別名路由 |
| `/my-subscriptions` | `PublicSubscriptionListPage` | 公開 | 以 email 查詢並管理自己的訂閱 |
| `/login` | `LoginPage` | 公開（已登入則跳轉 `/`） | 一般用戶登入 |
| `/register` | `RegisterPage` | 公開（已登入則跳轉 `/`） | 用戶註冊 |
| `/admin` | `SubscriptionListPage` | `ProtectedRoute`（一般 JWT） | 登入用戶的訂閱管理清單 |
| `/subscriptions/:id/edit` | `EditSubscriptionPage` | `ProtectedRoute`（一般 JWT） | 編輯訂閱設定 |
| `/history` | `HistoryPage` | `ProtectedRoute`（一般 JWT） | 寄信歷史紀錄 |
| `/admin/login` | `AdminLoginPage` | 公開 | 管理員專用登入頁 |
| `/admin/subscriptions` | `AdminSubscriptionsPage` | `AdminRoute`（admin JWT） | 管理員後台：所有訂閱者清單 |
| `*` | — | — | 未知路徑一律重導至 `/` |

### 路由守衛機制

```
PublicRoute（/login, /register）
  └── localStorage 有 access_token？
        是 → <Navigate to="/" replace />
        否 → 渲染頁面

ProtectedRoute（/admin, /subscriptions/:id/edit, /history）
  └── localStorage 有 access_token？
        否 → <Navigate to="/login" replace />
        是 → 渲染頁面

AdminRoute（/admin/subscriptions）
  └── localStorage 有 admin_access_token？
        否 → <Navigate to="/admin/login" replace />
        是 → 渲染頁面；後端 API 401/403 時清除 token 並跳轉
```

### Token 儲存策略

| Token Key | 儲存位置 | 使用場景 |
|-----------|----------|----------|
| `access_token` | localStorage | 一般用戶登入後寫入 |
| `admin_access_token` | localStorage | 管理員登入後寫入（與一般 token 完全分離） |

登入時（`LoginPage` 或 `AdminLoginPage`），前端解碼 JWT payload 中的 `is_admin` 欄位：
- `is_admin === true` → 存入 `admin_access_token`，跳轉至 `/admin/subscriptions`
- 其他 → 存入 `access_token`，跳轉至 `/`
