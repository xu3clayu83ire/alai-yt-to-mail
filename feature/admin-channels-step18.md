# admin-channels-step18

## 功能名稱

管理員頻道白名單 — 前端改版（訂閱頁 + 管理員頻道管理頁）

## 目標

配合 step17 的後端改版，完成前端的對應更改：
1. 重寫 `AddSubscriptionPage.tsx`：移除步驟 1（URL 輸入 + verify），改為頻道下拉選單
2. 新增 `AdminChannelsPage.tsx`：管理員頻道管理頁面（列出、新增、修改、刪除）
3. 刪除 `frontend/src/api/channels.ts`（廢棄的 channels verify API）
4. 更新 `frontend/src/types/index.ts`（新增頻道相關型別）
5. 新增 `frontend/src/api/adminChannels.ts`（管理員頻道 API）
6. 新增 `frontend/src/api/publicChannels.ts`（公開頻道列表 API）
7. 更新前端路由（`App.tsx`）

---

## 技術規格

### 前端技術棧（與現有保持一致）

- React + TypeScript（Vite）
- react-hook-form + zod + @hookform/resolvers
- axios（已設定 base URL 與 JWT 攔截器）
- react-router-dom v6
- Tailwind CSS（現有 UI 風格）

---

### API 介面（前端使用）

#### 公開頻道列表
- `GET /public/channels` → `PublicChannelItem[]`
- 無需認證

#### 管理員頻道 CRUD
- `POST /admin/channels` → `ChannelItem`（需 admin JWT）
- `GET /admin/channels` → `ChannelItem[]`（需 admin JWT）
- `PATCH /admin/channels/{channel_id}` → `ChannelItem`（需 admin JWT）
- `DELETE /admin/channels/{channel_id}` → `{ message: string; cancelled_subscriptions: number }`（需 admin JWT）

---

### 資料模型（TypeScript 型別）

新增至 `frontend/src/types/index.ts`：

```typescript
/** 公開可訂閱頻道項目（下拉選單使用） */
export interface PublicChannelItem {
  channel_id: string;
  channel_name: string;
  channel_url: string;
}

/** 管理員頻道項目（含建立時間） */
export interface ChannelItem {
  channel_id: string;
  channel_name: string;
  channel_url: string;
  created_at: string;
}

/** 新增頻道請求 */
export interface ChannelCreateRequest {
  channel_id: string;
  channel_name: string;
  channel_url: string;
}

/** 更新頻道請求（欄位選填） */
export interface ChannelUpdateRequest {
  channel_name?: string;
  channel_url?: string;
}

/** 刪除頻道回應 */
export interface ChannelDeleteResponse {
  message: string;
  cancelled_subscriptions: number;
}
```

同時，移除現有的 `ChannelVerifyRequest` 與 `ChannelVerifyResponse`（廢棄）。

---

### 檔案變更清單

#### 刪除檔案
- `yt-to-mail/frontend/src/api/channels.ts`（整個檔案）

#### 新增檔案

**`yt-to-mail/frontend/src/api/publicChannels.ts`**

提供 `getPublicChannels(): Promise<PublicChannelItem[]>` 函式。
使用 axios 呼叫 `GET /public/channels`，無需 Authorization header。

**`yt-to-mail/frontend/src/api/adminChannels.ts`**

提供以下函式（均需 admin JWT，由 axios 攔截器自動附加 — 但 admin token 存放在不同 key，需確認現有 adminAxios 或另行處理）：

- `adminCreateChannel(data: ChannelCreateRequest): Promise<ChannelItem>`
- `adminListChannels(): Promise<ChannelItem[]>`
- `adminUpdateChannel(channelId: string, data: ChannelUpdateRequest): Promise<ChannelItem>`
- `adminDeleteChannel(channelId: string): Promise<ChannelDeleteResponse>`

注意：管理員 API 使用 admin JWT，需與 `admin.ts` 中相同的 header 附加方式（參考現有 `frontend/src/api/admin.ts`）。

**`yt-to-mail/frontend/src/pages/AdminChannelsPage.tsx`**

管理員頻道管理頁面，需 admin token（使用 `AdminRoute` 守衛）。

功能：
- 頁面載入時 `GET /admin/channels` 取得頻道列表
- 顯示頻道表格：頻道名稱、channel_id、URL、建立時間、操作（修改、刪除）
- 新增頻道表單（inline 或 modal 皆可）：輸入 channel_id、channel_name、channel_url，送出呼叫 `POST /admin/channels`
- 刪除按鈕點擊後顯示確認對話框，說明：「刪除後將同時取消所有訂閱此頻道的用戶，並發送通知信。共 N 名訂閱者將受影響。」（N 顯示於確認後的回應 `cancelled_subscriptions`，或刪除前不顯示數字、確認後再顯示結果）
- 修改功能：點擊修改後顯示 inline 編輯欄位（channel_name、channel_url），送出呼叫 `PATCH /admin/channels/{channel_id}`
- 操作成功後重新 fetch 頻道列表更新畫面
- 錯誤處理：409（重複 channel_id）顯示「此頻道 ID 已存在」；404 顯示「頻道不存在」；403 顯示「無管理員權限」

#### 修改現有檔案

**`yt-to-mail/frontend/src/pages/AddSubscriptionPage.tsx`（重寫）**

核心改動：
- 移除 step 1（URL 輸入 + verify 按鈕）、所有 `channelForm` 相關 state 與邏輯
- 移除 `verifyChannel` import（`channels.ts` 已刪除）
- 移除 `ChannelVerifyResponse` type import
- 移除步驟指示器中的「步驟 1：確認頻道」（改為單步驟流程，或保留步驟指示器僅顯示「選擇頻道」和「填寫設定」兩步驟但邏輯改為：步驟 1 = 選擇下拉頻道，步驟 2 = 填寫訂閱設定）

重寫後的頁面邏輯：

```
步驟 1 — 選擇頻道（下拉選單）：
  - 頁面載入時呼叫 GET /public/channels，取得 PublicChannelItem[]
  - 顯示 <select> 讓用戶選擇頻道
  - 選擇後儲存 selectedChannel: PublicChannelItem
  - 點擊「下一步」進入步驟 2（無需 API 呼叫）
  - 若頻道列表為空，顯示「目前尚無可訂閱頻道，請聯繫管理員」

步驟 2 — 填寫訂閱設定（與現有相同）：
  - 顯示已選頻道名稱（唯讀）
  - 收件信箱、發送時間、語速、自動取消天數欄位
  - 送出時呼叫 POST /public/subscribe，body 中 channel_url 改為 selectedChannel.channel_url

成功狀態：
  - 與現有相同（「再訂閱一個」+ 「查看我的訂閱」）
  - handleReset 重置時回到步驟 1
```

表單 schema 調整：
- 移除 `channelUrlSchema`（不再需要）
- 新增 step 1 的 zod schema：`channelSelectSchema = z.object({ channel_id: z.string().min(1, '請選擇頻道') })`

保留不變的部分：
- Hero 區塊、Feature 卡片、CTA 區塊（行銷內容）
- 步驟 2 所有表單欄位與驗證邏輯
- `resolveSubmitError` 函式（調整：移除 verify 相關的 400 訊息）
- `localTimeToUtc` 換算邏輯

**`yt-to-mail/frontend/src/types/index.ts`**
- 新增 `PublicChannelItem`、`ChannelItem`、`ChannelCreateRequest`、`ChannelUpdateRequest`、`ChannelDeleteResponse`
- 移除 `ChannelVerifyRequest`、`ChannelVerifyResponse`（如無其他地方引用）

**`yt-to-mail/frontend/src/App.tsx`**
- 新增 `/admin/channels` 路由，元件為 `AdminChannelsPage`，包裹於 `AdminRoute`
- 移除對 `AddSubscriptionPage` 中 channels 相關的任何 prop 傳入（若有）

---

### 頁面路由

| 路徑 | 元件 | 守衛 |
|------|------|------|
| `/admin/channels` | `AdminChannelsPage` | `AdminRoute` |

現有路由不受影響。

---

### UI 設計規範

維持現有 Tailwind CSS 風格：
- 管理員頁面使用 `bg-white rounded-lg shadow-sm border` 卡片樣式
- 刪除確認使用 `window.confirm()` 或 inline 確認 UI（與現有 `AdminSubscriptionsPage.tsx` 保持一致）
- 新增/編輯表單使用 `react-hook-form` + `zod`

---

## 驗收條件

### 前端建置
- [ ] `npm run build` 無 TypeScript 錯誤
- [ ] `frontend/src/api/channels.ts` 不存在
- [ ] `AddSubscriptionPage.tsx` 不含 `verifyChannel` import
- [ ] `AddSubscriptionPage.tsx` 不含 `channel_url` 文字輸入欄位

### AddSubscriptionPage 功能
- [ ] 頁面載入時自動呼叫 `GET /public/channels`，顯示頻道下拉選單
- [ ] 下拉選單未選擇頻道時，無法進入步驟 2（顯示驗證錯誤）
- [ ] 選擇頻道後進入步驟 2，顯示頻道名稱（唯讀）
- [ ] 步驟 2 送出呼叫 `POST /public/subscribe`，body 含正確的 `channel_url`
- [ ] 成功後顯示確認訊息，「再訂閱一個」重置回步驟 1
- [ ] 頻道列表為空時顯示友善提示訊息

### AdminChannelsPage 功能
- [ ] 存取 `/admin/channels` 未登入時導向 `/admin/login`
- [ ] 以 admin 身份登入後可存取 `/admin/channels`
- [ ] 頁面顯示所有頻道，含頻道名稱、channel_id、URL
- [ ] 新增頻道成功後列表更新
- [ ] 新增重複 channel_id 顯示「此頻道 ID 已存在」錯誤
- [ ] 修改頻道成功後列表更新
- [ ] 刪除頻道前顯示確認對話框（含警告：將取消所有訂閱並通知用戶）
- [ ] 刪除成功後列表更新，顯示已取消的訂閱數量

### 型別安全
- [ ] `ChannelVerifyRequest`、`ChannelVerifyResponse` 從 types/index.ts 移除
- [ ] `PublicChannelItem`、`ChannelItem` 等新型別已正確定義
- [ ] 所有 API 函式具備 TypeScript 回傳型別標注

---

## 工作分派（單 Coder 執行）

| 優先順序 | 負責檔案 | 任務描述 |
|---------|---------|---------|
| 1 | `frontend/src/types/index.ts` | 新增頻道相關型別，移除廢棄的 ChannelVerify 型別 |
| 2 | `frontend/src/api/publicChannels.ts` | 新增公開頻道列表 API 函式 |
| 3 | `frontend/src/api/adminChannels.ts` | 新增管理員頻道 CRUD API 函式 |
| 4 | `frontend/src/pages/AddSubscriptionPage.tsx` | 重寫：移除 verify 流程，改為頻道下拉選單 |
| 5 | `frontend/src/pages/AdminChannelsPage.tsx` | 新增管理員頻道管理頁面 |
| 6 | `frontend/src/App.tsx` | 新增 /admin/channels 路由 |
| 7 | `frontend/src/api/channels.ts` | 刪除整個檔案 |

### 依賴順序
- 步驟 1（types）必須最先完成（其他步驟依賴型別定義）
- 步驟 2、3（API 函式）依賴步驟 1，可平行執行
- 步驟 4（AddSubscriptionPage 重寫）依賴步驟 1、2
- 步驟 5（AdminChannelsPage）依賴步驟 1、3
- 步驟 6（App.tsx）依賴步驟 5
- 步驟 7（刪除 channels.ts）必須在步驟 4 完成後執行（確認不再被引用）

---

## 開發階段拆分

- Step 18-A：型別定義更新（`types/index.ts`）
- Step 18-B：API 函式層（`publicChannels.ts`、`adminChannels.ts`）
- Step 18-C：AddSubscriptionPage 重寫
- Step 18-D：AdminChannelsPage 新增 + App.tsx 路由更新
- Step 18-E：刪除廢棄檔案（`api/channels.ts`）+ `npm run build` 驗證

---

## 注意事項與限制

1. **admin JWT 傳遞方式**：參考現有 `frontend/src/api/admin.ts` 的實作，admin token 存放於 localStorage 的不同 key（`adminToken`），在 API 呼叫時手動附加 `Authorization: Bearer {adminToken}` header，不依賴一般 user 的 axios 攔截器。`adminChannels.ts` 需使用相同方式。

2. **`AddSubscriptionPage.tsx` 保留行銷內容**：Hero 區塊、Feature 卡片、CTA 區塊的 JSX 完整保留，只修改表單流程部分。

3. **下拉選單 loading 狀態**：`GET /public/channels` 呼叫期間，下拉選單顯示「載入中...」並 disabled。

4. **頻道為空的 edge case**：若 `GET /public/channels` 回傳空陣列，步驟 1 顯示「目前尚無可訂閱頻道，請聯繫管理員」且無法提交。

5. **`ChannelVerifyResponse` 移除的影響**：確認整個前端專案中只有 `AddSubscriptionPage.tsx` 使用此型別，移除前確認無其他引用。

6. **`publicSubscribe` API 的 `channel_url` 來源改變**：從前端角度，`channel_url` 現在來自 `selectedChannel.channel_url`（下拉選單選擇後取得），後端 `POST /public/subscribe` 的接口不變，前端直接傳入此 URL 即可。

7. **AdminChannelsPage 的 PATCH 實作**：`channel_id` 不可修改（為 PK），只開放 `channel_name` 與 `channel_url` 的編輯。
