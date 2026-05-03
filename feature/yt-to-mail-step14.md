# yt-to-mail-step14：v3 前端管理員後台

## 前提條件與相依 Step

- **先決條件**：step11 已完成（`POST /auth/login` admin 判斷 + `GET/DELETE /admin/subscriptions` API 可用）
- **相依關係**：可在 step12、step13 同時進行，或任一 Coder 接手
- **後續相依**：無

---

## 功能名稱

前端管理員後台：`/admin/login` + `/admin/subscriptions`

---

## 目標

新增管理員專用的兩個頁面：
1. `/admin/login`：管理員登入頁，取得含 `is_admin` 的 JWT 並存入 localStorage
2. `/admin/subscriptions`：全表訂閱管理頁，支援 email 篩選、取消訂閱操作

---

## 技術規格

### 影響檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `frontend/src/pages/AdminLoginPage.tsx` | **新增** | 管理員登入頁 |
| `frontend/src/pages/AdminSubscriptionsPage.tsx` | **新增** | 管理員訂閱管理頁 |
| `frontend/src/api/admin.ts` | **新增** | admin API 呼叫函式 |
| `frontend/src/components/AdminRoute.tsx` | **新增** | admin JWT 驗證路由守衛 |
| `frontend/src/App.tsx` | **修改** | 新增 `/admin/login` 與 `/admin/subscriptions` 路由 |
| `frontend/src/utils/storage.ts` | **修改** | 新增 admin token 存取函式 |
| `frontend/src/types/index.ts` | **修改** | 新增 admin 相關型別 |

---

### 路由新增（App.tsx）

```tsx
{/* 管理員路由 */}
<Route path="/admin/login" element={<AdminLoginPage />} />
<Route
  path="/admin/subscriptions"
  element={
    <AdminRoute>
      <AdminSubscriptionsPage />
    </AdminRoute>
  }
/>
```

---

### storage.ts 更新

新增 admin token 獨立存取函式（與一般用戶 token 分開存放）：

```typescript
const ADMIN_TOKEN_KEY = 'admin_access_token';

/**
 * 儲存管理員 JWT token 至 localStorage
 */
export function setAdminToken(token: string): void { ... }

/**
 * 取得管理員 JWT token
 */
export function getAdminToken(): string | null { ... }

/**
 * 清除管理員 JWT token
 */
export function removeAdminToken(): void { ... }
```

---

### AdminRoute 元件規格

```tsx
/**
 * 管理員路由守衛：驗證 admin token 存在
 * admin token 不存在時重導至 /admin/login
 * 注意：僅驗證 token 存在，不驗證 is_admin 欄位（依賴後端 API 的 403 回應）
 */
export function AdminRoute({ children }: { children: React.ReactNode }): JSX.Element {
  const token = getAdminToken();
  if (!token) {
    return <Navigate to="/admin/login" replace />;
  }
  return <>{children}</>;
}
```

---

### AdminLoginPage 規格（/admin/login）

#### UI 元素

- 頁面標題：「管理員登入」
- Email 輸入框（type="email"，必填）
- Password 輸入框（type="password"，必填）
- 「登入」按鈕
- 錯誤訊息區（401 時顯示「Email 或密碼錯誤」）

#### 登入邏輯

1. 呼叫 `POST /auth/login`（現有端點，但 email 為 admin email）
2. 成功後以 `setAdminToken(token)` 存入 localStorage
3. 跳轉至 `/admin/subscriptions`
4. 失敗（401）顯示錯誤訊息

```tsx
/**
 * 管理員登入頁面
 * 使用現有 POST /auth/login 端點，以 admin email 登入取得含 is_admin 的 JWT
 */
export function AdminLoginPage(): JSX.Element { ... }
```

---

### AdminSubscriptionsPage 規格（/admin/subscriptions）

#### 頁面功能

- 頁首：「訂閱管理後台」標題 + 登出按鈕
- Email 篩選欄位（輸入後觸發 `GET /admin/subscriptions?email=xxx`）
- 「查詢全部」按鈕（清空篩選，查詢全表）
- 訂閱資料表格

#### 資料表格欄位

| 欄位 | 說明 |
|------|------|
| 用戶 Email | `user_id`（即 email） |
| 頻道名稱 | `channel_name`（可點擊，連結至 `channel_url`） |
| 收件信箱 | `recipient_email` |
| 發送時間 | `send_time`（UTC，顯示為 UTC HH:MM，不換算） |
| 語速 | `audio_speed` |
| 無新影片 | `no_new_video_days` / `auto_cancel_days` |
| 建立時間 | `created_at`（UTC 格式） |
| 狀態 | `is_active`（「啟用」/「停用」標籤） |
| 操作 | 「取消訂閱」按鈕（紅色） |

> 管理員後台的時間顯示維持 UTC，方便除錯，不做本地時區換算。

#### 頁面狀態管理

```typescript
interface AdminPageState {
  subscriptions: AdminSubscriptionItem[];
  isLoading: boolean;
  error: string | null;
  filterEmail: string;
  deletingId: string | null;
}
```

#### 取消訂閱流程

1. 點擊「取消訂閱」按鈕
2. `window.confirm`：「確定要取消訂閱「{channel_name}」（{user_id}）嗎？」
3. 確認後呼叫 `DELETE /admin/subscriptions/{id}`（帶 admin JWT）
4. 成功後從列表移除
5. 若 JWT 過期（403/401 response），清除 admin token 並跳轉至 `/admin/login`

#### 登出功能

```typescript
/**
 * 管理員登出：清除 admin token 並跳轉至 /admin/login
 */
function handleLogout(): void {
  removeAdminToken();
  navigate('/admin/login');
}
```

---

### api/admin.ts 規格

```typescript
/**
 * 管理員 API 呼叫函式模組
 * 所有請求需帶 admin JWT（從 getAdminToken() 取得）
 */

import axios from 'axios';
import { getAdminToken } from '../utils/storage';

export interface AdminSubscriptionItem {
  id: string;
  user_id: string;
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
  is_active: boolean;
  auto_cancel_days: number;
  no_new_video_days: number;
  created_at: string;
}

/**
 * 建立帶 admin JWT 的 axios 請求 headers
 */
function adminHeaders(): Record<string, string> {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * 查詢所有訂閱（可選 email 篩選）
 */
export async function adminListSubscriptions(
  email?: string
): Promise<AdminSubscriptionItem[]> { ... }

/**
 * 刪除指定訂閱（admin 強制刪除）
 */
export async function adminDeleteSubscription(id: string): Promise<void> { ... }
```

---

### types/index.ts 更新

新增 admin 相關型別：

```typescript
/**
 * 管理員後台訂閱項目型別
 */
interface AdminSubscriptionItem {
  id: string;
  user_id: string;
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
  is_active: boolean;
  auto_cancel_days: number;
  no_new_video_days: number;
  created_at: string;
}
```

---

### 401/403 全域處理

`api/admin.ts` 中的所有請求若收到 401 或 403，應清除 admin token 並拋出特定錯誤，由頁面元件捕捉後跳轉至 `/admin/login`。

不在現有 `apiClient`（`api/client.ts`）的攔截器中處理 admin token，以免混淆一般用戶的登出邏輯。

---

## 驗收標準

- [ ] 直接存取 `/admin/subscriptions`（無 admin token）自動重導至 `/admin/login`
- [ ] 以正確 admin 帳密登入後跳轉至 `/admin/subscriptions`
- [ ] 以錯誤密碼登入顯示「Email 或密碼錯誤」
- [ ] `/admin/subscriptions` 頁面載入時呼叫 `GET /admin/subscriptions` 並顯示全表
- [ ] Email 篩選欄位輸入後正確呼叫 `GET /admin/subscriptions?email=xxx`
- [ ] 每筆訂閱顯示：用戶 email、頻道名稱、發送時間、語速、無新影片計數、狀態
- [ ] 「取消訂閱」確認後呼叫 `DELETE /admin/subscriptions/{id}` 並從列表移除
- [ ] 登出後清除 admin token，重導至 `/admin/login`
- [ ] `npm run build` 無 TypeScript 錯誤

---

## 工作分派

### 本 Step 指派
- **任一 Coder**：step11 完成後，Coder A 或 Coder B 均可接手

### 平行協作
- 可與 step12、step13 同時進行（不同頁面，無程式碼衝突）

---

## 注意事項與限制

- Admin token 與一般用戶 token 分開存放於 localStorage（key 不同），互不影響
- 管理員後台時間顯示維持 UTC 格式，方便管理除錯，不做本地時區換算
- 後台頁面不使用現有 `Layout.tsx`（導覽列不適合管理後台），獨立設計簡單頁首
- Admin JWT 解碼後含 `is_admin: true`，前端不主動解碼驗證（依賴後端 403）
- 管理員路徑（`/admin/*`）需確保不被 `PublicRoute` 邏輯影響（`/admin/login` 即使已登入一般帳號也可存取）
- 所有元件必須包含繁體中文函式級註解
- TypeScript 嚴格模式，禁止 `any` 型別
