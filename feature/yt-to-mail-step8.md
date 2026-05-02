# yt-to-mail-step8：Phase 3 — 前端（React）

## 功能名稱

前端 Web 應用程式：React + TypeScript + Vite

---

## 目標

建立 yt-to-mail 系統的前端介面，提供用戶：
- 帳號登入與註冊
- 訂閱管理（查看、新增含頻道確認、編輯、刪除、啟用/停用）
- 歷史紀錄查閱

前端為純靜態網站，部署至 S3（Phase 4 完成），透過 Lambda Function URL 呼叫後端 API。所有 API 呼叫使用 JWT Bearer Token 認證，時間顯示轉換為瀏覽器本地時區。

---

## 技術規格

### 技術棧

| 元件 | 版本 | 說明 |
|---|---|---|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 型別安全 |
| Vite | 5.x | 建置工具 |
| React Router | 6.x | 前端路由 |
| axios | 1.x | HTTP 客戶端 |
| React Hook Form | 7.x | 表單管理 |
| Zod | 3.x | 表單驗證 schema |
| TanStack Query | 5.x | API 資料快取與狀態管理 |

> 樣式方案：Tailwind CSS（若 cdk-coder 評估過於複雜可改用 CSS Modules）

---

### 目錄結構

```
frontend/
  src/
    api/
      client.ts          # axios 實例，含攔截器設定
      auth.ts            # auth API 呼叫函式
      subscriptions.ts   # subscriptions API 呼叫函式
      history.ts         # history API 呼叫函式
      channels.ts        # channels/verify API 呼叫函式
    components/
      Layout.tsx          # 共用版面（Header、Nav、Footer）
      ProtectedRoute.tsx  # 需要登入的路由保護
      SubscriptionCard.tsx # 訂閱卡片元件（列表顯示用）
      HistoryItem.tsx     # 歷史紀錄列表項目元件
    pages/
      LoginPage.tsx       # 登入頁面
      RegisterPage.tsx    # 註冊頁面
      SubscriptionListPage.tsx  # 訂閱列表頁面（首頁）
      AddSubscriptionPage.tsx   # 新增訂閱頁面
      EditSubscriptionPage.tsx  # 編輯訂閱頁面
      HistoryPage.tsx     # 歷史紀錄頁面
    hooks/
      useAuth.ts          # 認證狀態管理 hook
    utils/
      timezone.ts         # 時區轉換工具函式
      storage.ts          # localStorage JWT 存取工具
    types/
      index.ts            # 所有 TypeScript 型別定義
    App.tsx               # 路由設定
    main.tsx              # 應用程式入口
  .env                    # 本機開發環境變數（不納入版控）
  .env.example            # 環境變數範本
  .env.production         # 生產環境變數（build 時使用）
  vite.config.ts
  tsconfig.json
  package.json
```

---

### 路由規劃

| 路徑 | 元件 | 需要登入 | 說明 |
|---|---|---|---|
| `/login` | LoginPage | 否 | 已登入則重導至 `/` |
| `/register` | RegisterPage | 否 | 已登入則重導至 `/` |
| `/` | SubscriptionListPage | 是 | 顯示我的訂閱清單 |
| `/subscriptions/add` | AddSubscriptionPage | 是 | 新增訂閱（含頻道確認步驟） |
| `/subscriptions/:id/edit` | EditSubscriptionPage | 是 | 編輯訂閱 |
| `/history` | HistoryPage | 是 | 歷史紀錄 |

未登入存取需要登入的路由時，自動重導至 `/login`。

---

### TypeScript 型別定義（types/index.ts）

```typescript
// 用戶認證相關
interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}

// 訂閱相關
interface Subscription {
  id: string;
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;        // UTC HH:MM（API 回傳）
  is_active: boolean;
  created_at: string;
}

interface SubscriptionCreateRequest {
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;        // UTC HH:MM（送出前換算）
}

interface SubscriptionUpdateRequest {
  recipient_email?: string;
  audio_speed?: number;
  send_time?: string;       // UTC HH:MM
  is_active?: boolean;
}

// 歷史紀錄相關
type HistoryStatus = "done" | "failed" | "skipped_language";

interface HistoryItem {
  id: string;
  subscription_id: string;
  video_id: string;
  video_title: string;
  sent_at: string;          // ISO 8601 UTC
  status: HistoryStatus;
  error_message?: string;
}

// 頻道確認相關
interface ChannelVerifyRequest {
  channel_url: string;
}

interface ChannelVerifyResponse {
  channel_url: string;
  channel_id: string;
  channel_name: string;
}

// API 錯誤
interface ApiError {
  detail: string;
}
```

---

### axios 攔截器規格（api/client.ts）

**axios 實例設定**：
```typescript
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json"
  }
});
```

**Request 攔截器**：
- 從 localStorage 讀取 `access_token`
- 若存在，自動附加 `Authorization: Bearer <token>` header

**Response 攔截器**：
- HTTP 401 回應時：清除 localStorage 中的 `access_token`，重導至 `/login`
- 其他錯誤：正常拋出，由呼叫端處理

---

### 時區處理規格（utils/timezone.ts）

**問題**：後端 API 儲存與回傳的 `send_time` 是 UTC 格式（`HH:MM`），前端需要顯示本地時間，且送出時需換算回 UTC。

**工具函式規格**：

```typescript
/**
 * 將 UTC HH:MM 時間字串轉換為瀏覽器本地時間 HH:MM
 * 例：UTC 14:00 → 台灣時間 22:00
 */
function utcTimeToLocal(utcTime: string): string

/**
 * 將瀏覽器本地時間 HH:MM 換算為 UTC HH:MM
 * 例：台灣時間 22:00 → UTC 14:00
 */
function localTimeToUtc(localTime: string): string

/**
 * 將 ISO 8601 UTC 時間戳記轉換為本地可讀格式
 * 例："2026-05-01T14:00:00Z" → "2026/05/01 22:00"
 */
function formatUtcTimestamp(utcTimestamp: string): string
```

**換算邏輯**：
1. 使用 `Intl.DateTimeFormat` 取得瀏覽器時區偏移量（分鐘）
2. 以 `Date` 物件進行換算，處理跨日情況（00:00 ～ 23:59 環狀）
3. 回傳格式統一為 `HH:MM`（補零）

---

### 頁面功能規格

#### LoginPage（/login）

- Email 輸入欄位（type="email"，必填）
- Password 輸入欄位（type="password"，必填）
- 提交按鈕「登入」
- 登入成功：將 access_token 存入 localStorage，重導至 `/`
- 登入失敗（401）：顯示錯誤訊息「Email 或密碼錯誤」
- 頁面底部連結：「還沒有帳號？立即註冊」→ `/register`

#### RegisterPage（/register）

- Email 輸入欄位（type="email"，必填）
- Password 輸入欄位（type="password"，必填，最少 8 字元）
- Confirm Password 輸入欄位（必填，需與 Password 一致）
- 提交按鈕「註冊」
- 註冊成功：自動以同帳密呼叫登入 API，取得 token 後重導至 `/`
- 註冊失敗（409）：顯示「此 Email 已被使用」
- 頁面底部連結：「已有帳號？前往登入」→ `/login`

#### SubscriptionListPage（/）

- 頂部顯示：「我的訂閱（X/5）」（X 為當前訂閱數）
- 每個訂閱以 SubscriptionCard 元件顯示：
  - 頻道名稱與 URL
  - 收件信箱
  - 每日發送時間（轉換為本地時間顯示）
  - 語速
  - 啟用/停用切換開關（呼叫 PUT API 更新 is_active）
  - 編輯按鈕 → `/subscriptions/:id/edit`
  - 刪除按鈕（確認對話框後呼叫 DELETE API）
- 若無訂閱：顯示「尚無訂閱，立即新增」按鈕
- 右上角「新增訂閱」按鈕（訂閱數 ≥ 5 時顯示為 disabled）→ `/subscriptions/add`

#### AddSubscriptionPage（/subscriptions/add）

**步驟設計（兩步驟流程）**：

**步驟 1：輸入頻道 URL 並確認**
- 頻道 URL 輸入欄位（預設值：`https://www.youtube.com/@智慧之聲-b9z`，供開發測試使用）
- 「確認頻道」按鈕：呼叫 `POST /channels/verify`
- 成功後顯示頻道資訊（channel_name、channel_url）
- 確認正確後進入步驟 2
- 錯誤時顯示「無法識別此頻道 URL，請確認格式」

**步驟 2：填寫訂閱設定**
- 頻道資訊（唯讀顯示，已從步驟 1 帶入）
- 收件信箱（type="email"，必填）
- 每日發送時間（time picker，顯示本地時間，送出前換算 UTC）
- 語速選擇（下拉選單：0.5x, 0.75x, 0.85x, 1.0x, 1.5x, 2.0x，預設 1.0x）
- 「建立訂閱」按鈕：呼叫 `POST /subscriptions`
- 成功後重導至 `/`
- 失敗（400 上限）：顯示「已達 5 個訂閱上限」

#### EditSubscriptionPage（/subscriptions/:id/edit）

- 頁面載入時呼叫 `GET /subscriptions`，找到對應訂閱預填表單
- 可編輯欄位：收件信箱、每日發送時間（本地時間顯示）、語速、是否啟用
- 頻道資訊唯讀顯示（不允許修改）
- 「儲存」按鈕：呼叫 `PUT /subscriptions/:id`
- 成功後重導至 `/`
- 「取消」按鈕：返回 `/`

#### HistoryPage（/history）

- 顯示歷史紀錄清單（依 sent_at 降序）
- 每筆顯示：影片標題、YouTube 連結（video_id 組成）、發送時間（本地時間）、狀態標籤
  - `done`：綠色標籤「已寄出」
  - `failed`：紅色標籤「失敗」，hover 顯示 error_message（若有）
  - `skipped_language`：灰色標籤「已跳過（非英文）」
- 預設載入 20 筆，有「載入更多」按鈕（limit 累加）

---

### 環境變數規格（.env）

| 變數名稱 | 說明 | 範例值 |
|---|---|---|
| `VITE_API_BASE_URL` | Lambda Function URL | `https://xxxxx.lambda-url.ap-northeast-1.on.aws` |

`.env.production` 與 `.env` 格式相同，值為實際生產環境 URL。

---

### 表單驗證（Zod schema）

**登入/註冊**：
```typescript
const loginSchema = z.object({
  email: z.string().email("請輸入有效的 Email 格式"),
  password: z.string().min(8, "密碼至少 8 個字元")
});
```

**新增/編輯訂閱**：
```typescript
const subscriptionSchema = z.object({
  recipient_email: z.string().email("請輸入有效的 Email 格式"),
  audio_speed: z.enum(["0.5", "0.75", "0.85", "1.0", "1.5", "2.0"]),
  send_time: z.string().regex(/^\d{2}:\d{2}$/, "時間格式錯誤"),
  is_active: z.boolean().optional()
});
```

---

## 實作步驟（供 cdk-coder 執行）

- Step 1：以 Vite 建立 React + TypeScript 專案（`npm create vite@latest frontend -- --template react-ts`）
- Step 2：安裝必要套件（react-router-dom、axios、react-hook-form、zod、@hookform/resolvers、@tanstack/react-query）
- Step 3：建立目錄結構（api/、components/、pages/、hooks/、utils/、types/）
- Step 4：實作 `types/index.ts`（所有型別定義）
- Step 5：實作 `utils/timezone.ts`（UTC ↔ 本地時間換算工具函式）
- Step 6：實作 `utils/storage.ts`（localStorage JWT 存取工具）
- Step 7：實作 `api/client.ts`（axios 實例 + Request/Response 攔截器）
- Step 8：實作 `api/auth.ts`、`api/subscriptions.ts`、`api/history.ts`、`api/channels.ts`
- Step 9：實作 `hooks/useAuth.ts`（JWT 存在狀態、logout 函式）
- Step 10：實作 `components/ProtectedRoute.tsx`（未登入自動重導）
- Step 11：實作 `App.tsx`（React Router 路由設定）
- Step 12：實作 `LoginPage.tsx` 與 `RegisterPage.tsx`
- Step 13：實作 `components/SubscriptionCard.tsx`
- Step 14：實作 `SubscriptionListPage.tsx`（含啟用切換、刪除確認）
- Step 15：實作 `AddSubscriptionPage.tsx`（兩步驟流程：頻道確認 → 填寫設定）
- Step 16：實作 `EditSubscriptionPage.tsx`
- Step 17：實作 `components/HistoryItem.tsx` 與 `HistoryPage.tsx`
- Step 18：建立 `.env.example` 與 `.env.production`（VITE_API_BASE_URL 留空）
- Step 19：確認 `vite.config.ts` 設定（build output 目錄為 `dist`）

---

## 驗收標準

- [ ] `npm run build` 無 TypeScript 錯誤，產生 `dist/` 靜態檔案
- [ ] `npm run dev` 本機可正常啟動，瀏覽器無 Console Error
- [ ] 未登入存取 `/` 自動重導至 `/login`
- [ ] 登入成功後 JWT 存入 localStorage，重導至首頁
- [ ] 首頁顯示訂閱列表，send_time 轉換為瀏覽器本地時間顯示
- [ ] 新增訂閱第一步驟成功呼叫 `/channels/verify` 並顯示頻道資訊
- [ ] 新增訂閱第二步驟 send_time 送出前換算為 UTC
- [ ] 已達 5 個訂閱時，「新增訂閱」按鈕顯示為 disabled
- [ ] 歷史紀錄依 sent_at 降序顯示，狀態標籤顏色正確
- [ ] axios 攔截器在收到 401 回應時自動清除 token 並跳轉登入頁
- [ ] 所有 API 呼叫正確附加 Authorization header

---

## 注意事項與限制

- `VITE_API_BASE_URL` 以 Vite 的 `import.meta.env.VITE_*` 讀取，不使用 `process.env`
- `send_time` 在前端統一以本地時間顯示，送出 API 前換算為 UTC，避免用戶混淆
- JWT 存於 localStorage（原型階段，正式版改 HttpOnly Cookie）
- React Router 的 SPA 路由在 S3 直接存取子路徑時會 404，需在 CloudFront 設定自訂錯誤頁（Phase 4 處理）
- 所有函式與 React 元件必須包含繁體中文函式級註解
- TypeScript 嚴格模式，禁止 `any` 型別
