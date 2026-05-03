# yt-to-mail-step12：v3 前端公開訂閱頁

## 前提條件與相依 Step

- **先決條件**：step10 已完成（`POST /public/subscribe` API 可用）
- **相依關係**：可與 step11 同時進行（前後端分離）；step15 無相依
- **後續相依**：step13 可在本 step 完成後接手，或由另一位 Coder 平行開發

---

## 功能名稱

前端公開訂閱頁：移除 ProtectedRoute + 新增 `auto_cancel_days` 欄位 + 根路由導向訂閱表單

---

## 目標

1. 將 `/subscriptions/add`（`AddSubscriptionPage`）改為公開頁面（移除 `ProtectedRoute` 包裝）
2. 表單加入 `auto_cancel_days` 欄位（數字輸入，min=1，預設 3）
3. 改用 `POST /public/subscribe`，Request Body 新增 `recipient_email` 欄位（不從 JWT 取得）
4. 送出後顯示成功訊息於原頁面（不跳轉）
5. 根路由 `/` 改為直接導向此公開訂閱頁（不再需要登入）

---

## 技術規格

### 影響檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `frontend/src/App.tsx` | **修改** | `/` 路由改導向 AddSubscriptionPage（公開），調整路由結構 |
| `frontend/src/pages/AddSubscriptionPage.tsx` | **修改** | 移除 ProtectedRoute 依賴、加入 recipient_email 欄位、改呼叫 public API、成功後顯示訊息 |
| `frontend/src/api/public.ts` | **新增** | 公開 API 呼叫函式 |
| `frontend/src/types/index.ts` | **修改** | 新增 PublicSubscribeRequest 型別 |

---

### 路由結構調整（App.tsx）

**現有根路由**（ProtectedRoute 包裝 SubscriptionListPage）改為：

```tsx
{/* 根路由改為公開訂閱頁，無需登入 */}
<Route path="/" element={<AddSubscriptionPage />} />

{/* 登入用戶的訂閱列表改至 /my-account（選項：保留或移除） */}
<Route
  path="/subscriptions"
  element={
    <ProtectedRoute>
      <Layout>
        <SubscriptionListPage />
      </Layout>
    </ProtectedRoute>
  }
/>
```

**完整新路由表**：

| 路徑 | 元件 | 需要登入 | 說明 |
|------|------|---------|------|
| `/` | AddSubscriptionPage（公開版） | 否 | 主要訂閱入口頁 |
| `/my-subscriptions` | PublicSubscriptionListPage | 否 | step13 實作 |
| `/subscriptions` | SubscriptionListPage | 是 | 原有 JWT 用戶訂閱列表（保留） |
| `/subscriptions/add` | AddSubscriptionPage | 否 | 同 `/`，別名路由 |
| `/subscriptions/:id/edit` | EditSubscriptionPage | 是 | 保留 |
| `/history` | HistoryPage | 是 | 保留 |
| `/login` | LoginPage | 否 | 保留 |
| `/register` | RegisterPage | 否 | 保留 |
| `/admin/login` | AdminLoginPage | 否 | step14 實作 |
| `/admin/subscriptions` | AdminSubscriptionsPage | 是（admin） | step14 實作 |
| `*` | 重導至 `/` | — | 未知路徑 |

---

### AddSubscriptionPage 改版規格

#### 表單欄位（公開版，使用 React Hook Form + Zod）

| 欄位名稱 | 類型 | 說明 | 驗證規則 |
|---------|------|------|---------|
| `recipient_email` | EmailStr | 收件信箱 | 必填，email 格式 |
| `channel_url` | string | YouTube 頻道 URL | 必填 |
| `audio_speed` | select | 語速倍率 | 0.5/0.75/0.85/1.0/1.5/2.0，預設 1.0 |
| `send_time` | time | 每日發送時間（本地時間顯示） | 必填，HH:MM 格式 |
| `auto_cancel_days` | number | 連續無新影片幾天後自動取消 | min=1，整數，預設 3 |

#### 步驟流程調整

**原兩步驟流程**（步驟 1：驗證頻道 → 步驟 2：填寫設定）**維持**，改為：

**步驟 1：輸入頻道 URL 並確認**
- 呼叫 `POST /channels/verify`（現有端點，無需 JWT）
- 顯示頻道名稱確認

**步驟 2：填寫訂閱設定（含公開版新欄位）**
- `recipient_email`（新增，必填）
- `send_time`（本地時間顯示，送出前換算 UTC）
- `audio_speed`
- `auto_cancel_days`（新增，預設 3）
- 呼叫 `POST /public/subscribe`

#### 成功行為改變

- **原行為**：成功後 `navigate('/')`
- **新行為**：保留在頁面，顯示成功訊息框：
  ```
  訂閱成功！系統將在每天指定時間寄送最新影片逐字稿至您的信箱。
  您可以到「查看我的訂閱」頁面管理訂閱。
  ```
  提供「再訂閱一個」按鈕（清空表單）與「查看我的訂閱」連結（跳轉至 `/my-subscriptions`）

#### 錯誤處理

| 狀態碼 | 顯示訊息 |
|-------|---------|
| 400（上限） | 此信箱已達 5 個訂閱上限 |
| 400（channel 無效） | 無法識別此頻道 URL，請確認格式 |
| 422 | 請確認欄位填寫正確 |
| 其他 | 送出失敗，請稍後再試 |

---

### 新增 api/public.ts

```typescript
/**
 * 公開 API 呼叫函式模組（無需 JWT）
 * 對應後端 /public/* 端點
 */

import { apiClient } from './client';

export interface PublicSubscribeRequest {
  recipient_email: string;
  channel_url: string;
  audio_speed: number;
  send_time: string;       // UTC HH:MM
  auto_cancel_days: number;
}

export interface PublicSubscriptionResponse {
  id: string;
  channel_url: string;
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
 * 公開訂閱：無需登入，直接送出
 */
export async function publicSubscribe(
  data: PublicSubscribeRequest
): Promise<PublicSubscriptionResponse> { ... }

/**
 * 以 email 查詢訂閱清單
 */
export async function getPublicSubscriptions(
  email: string
): Promise<PublicSubscriptionResponse[]> { ... }

/**
 * 以 email 驗證身分後刪除訂閱
 */
export async function deletePublicSubscription(
  id: string,
  email: string
): Promise<void> { ... }
```

---

### types/index.ts 更新

加入以下型別（不修改現有型別）：

```typescript
/**
 * 公開訂閱 API 相關型別
 */
interface PublicSubscribeRequest {
  recipient_email: string;
  channel_url: string;
  audio_speed: number;
  send_time: string;
  auto_cancel_days: number;
}

interface PublicSubscriptionItem {
  id: string;
  channel_url: string;
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

### Zod Schema 更新（AddSubscriptionPage 內部）

```typescript
const step2Schema = z.object({
  recipient_email: z.string().email('請輸入有效的 Email 格式'),
  audio_speed: z.enum(['0.5', '0.75', '0.85', '1.0', '1.5', '2.0']),
  send_time: z.string().regex(/^\d{2}:\d{2}$/, '時間格式錯誤'),
  auto_cancel_days: z
    .number({ invalid_type_error: '請輸入整數天數' })
    .int('請輸入整數天數')
    .min(1, '至少 1 天'),
});
```

---

### Layout 元件導覽列調整

公開版頁面不顯示需要登入的導覽項目。`Layout.tsx` 可保持現有邏輯（登出按鈕與登入連結根據 token 存在與否切換）。

公開頁（`/`）不需要 Layout 包裝，直接渲染 `AddSubscriptionPage`，或使用無導覽列的精簡 Layout。

---

## 驗收標準

- [ ] 直接存取 `/`（未登入）可正常顯示訂閱表單，不被跳轉至 `/login`
- [ ] 表單包含 `recipient_email`、`channel_url`、`audio_speed`、`send_time`、`auto_cancel_days` 欄位
- [ ] `auto_cancel_days` 欄位預設值為 3，min=1 驗證生效（輸入 0 顯示錯誤）
- [ ] 步驟 1 呼叫 `POST /channels/verify` 正確顯示頻道名稱
- [ ] 步驟 2 送出後呼叫 `POST /public/subscribe`（非 `POST /subscriptions`）
- [ ] `send_time` 顯示本地時間，送出前換算為 UTC
- [ ] 送出成功後顯示成功訊息，不跳轉頁面
- [ ] 成功訊息含「查看我的訂閱」連結（指向 `/my-subscriptions`）
- [ ] 錯誤（400/422）正確顯示對應訊息
- [ ] `npm run build` 無 TypeScript 錯誤
- [ ] 現有受保護路由（`/subscriptions`、`/history` 等）仍正常運作

---

## 工作分派

### 本 Step 指派
- **Coder B**（前端軌道）：step15 完成後，或與 step11 同時執行（前後端分離）

### 平行協作
- **Coder A** 同時執行 step11（後端管理員 API）
- step13 可在本 step 同時進行（公用 `api/public.ts` 已在本 step 建立）

---

## 注意事項與限制

- `POST /channels/verify` 現有端點是否需要 JWT 需確認；若需要，應改為無需 JWT，或在公開訂閱流程中以 public endpoint 替代
- `send_time` 的 UTC 換算邏輯已在 `utils/timezone.ts` 實作，直接複用
- 公開頁不需要 `ProtectedRoute`，但 `PublicRoute`（已登入重導）也不需要，直接渲染即可
- `auto_cancel_days` 在 HTML `<input type="number">` 中注意 valueAsNumber 的處理，避免 NaN
- 所有元件必須包含繁體中文函式級註解
- TypeScript 嚴格模式，禁止 `any` 型別
