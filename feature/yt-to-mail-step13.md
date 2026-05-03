# yt-to-mail-step13：v3 前端 Email 查詢頁

## 前提條件與相依 Step

- **先決條件**：step10 已完成（`GET/DELETE /public/subscriptions` API 可用）；step12 已建立 `api/public.ts`
- **相依關係**：可與 step11、step14 完全平行開發（前端軌道）
- **後續相依**：無

---

## 功能名稱

前端 Email 查詢頁：`/my-subscriptions`（無需登入）

---

## 目標

新增公開頁面 `/my-subscriptions`，讓任何知道自己訂閱 email 的用戶可以：
1. 輸入 email 查詢訂閱清單
2. 查看每筆訂閱的詳細資訊（含無新影片計數器）
3. 點擊「取消訂閱」按鈕，確認後刪除

---

## 技術規格

### 影響檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `frontend/src/pages/PublicSubscriptionListPage.tsx` | **新增** | Email 查詢頁主體 |
| `frontend/src/App.tsx` | **修改** | 新增 `/my-subscriptions` 路由（公開） |
| `frontend/src/api/public.ts` | **使用** | step12 已建立，本 step 直接使用 |

---

### 路由新增（App.tsx）

```tsx
{/* 公開訂閱查詢頁，無需登入 */}
<Route path="/my-subscriptions" element={<PublicSubscriptionListPage />} />
```

---

### PublicSubscriptionListPage 功能規格

#### 頁面狀態機

```
初始狀態（empty）
  │
  ↓ 用戶輸入 email 並送出
查詢中（loading）
  │
  ├── 查詢成功，有訂閱 → 顯示訂閱清單（list）
  ├── 查詢成功，無訂閱 → 顯示「尚未找到訂閱」（empty-result）
  └── 查詢失敗（網路錯誤） → 顯示錯誤訊息（error）
```

#### UI 佈局

**頁首區塊**：
- 頁面標題：「查看我的訂閱」
- 說明文字：「輸入您訂閱時使用的 Email，查看並管理您的訂閱。」
- Email 輸入框（type="email"，placeholder="your@email.com"）
- 「查詢」按鈕（loading 時 disabled + 顯示 spinner）

**訂閱清單區塊**（查詢成功後顯示）：

每筆訂閱以卡片形式呈現，包含：

| 顯示項目 | 說明 |
|---------|------|
| 頻道名稱 | `channel_name` |
| 頻道連結 | `channel_url`（可點擊） |
| 每日發送時間 | `send_time` 換算為本地時間顯示 |
| 語速 | `audio_speed`（例如：1.0x） |
| 建立時間 | `created_at`（換算為本地時間，格式 YYYY/MM/DD HH:mm） |
| 無新影片計數 | 「連續無新影片：N 天 / 設定上限：M 天」 |
| 狀態 | `is_active` → 顯示「啟用中」或「已停用」標籤 |
| 取消訂閱按鈕 | 紅色按鈕，點擊後顯示確認對話框 |

**「連續無新影片」顯示邏輯**：
- `no_new_video_days = 0`：顯示「尚無無新影片記錄」
- `no_new_video_days > 0`：顯示「連續無新影片：{no_new_video_days} 天 / 設定上限：{auto_cancel_days} 天」
- 若 `no_new_video_days >= auto_cancel_days - 1`（接近上限）：顯示橘色警示樣式

#### 取消訂閱流程

1. 點擊「取消訂閱」按鈕
2. 顯示 `window.confirm`（或 modal）：「確定要取消訂閱「{channel_name}」嗎？取消後需重新訂閱。」
3. 確認後呼叫 `DELETE /public/subscriptions/{id}?email={email}`
4. 成功後從清單移除該訂閱（不重新查詢，直接更新 state）
5. 顯示短暫的成功提示（Toast 或 inline 訊息）
6. 失敗時顯示錯誤訊息

---

### 元件結構（PublicSubscriptionListPage.tsx）

```tsx
/**
 * 公開訂閱查詢頁面
 * 無需登入，透過 email 查詢並管理訂閱
 */

interface PageState {
  email: string;
  subscriptions: PublicSubscriptionItem[] | null;
  isLoading: boolean;
  error: string | null;
  deletingId: string | null;
}

export function PublicSubscriptionListPage(): JSX.Element {
  const [state, setState] = useState<PageState>({...});

  /**
   * 執行 email 查詢，呼叫 GET /public/subscriptions?email=xxx
   */
  async function handleSearch(email: string): Promise<void> { ... }

  /**
   * 確認後刪除指定訂閱
   */
  async function handleDelete(id: string, channelName: string): Promise<void> { ... }

  return (
    <div>
      {/* 搜尋表單 */}
      {/* 訂閱清單 */}
      {/* 訂閱卡片 */}
    </div>
  );
}
```

---

### 訂閱卡片子元件（inline 或獨立元件）

```tsx
/**
 * 公開訂閱清單的單一訂閱卡片
 * 顯示頻道資訊、無新影片計數、取消訂閱按鈕
 */
interface PublicSubscriptionCardProps {
  subscription: PublicSubscriptionItem;
  onDelete: (id: string, channelName: string) => void;
  isDeleting: boolean;
}

function PublicSubscriptionCard(props: PublicSubscriptionCardProps): JSX.Element { ... }
```

---

### 無新影片計數顯示元件規格

```tsx
/**
 * 無新影片計數顯示元件
 * 依計數與上限決定顯示樣式（正常/警示）
 */
function NoDaysCounter({
  noDays,
  limit,
}: {
  noDays: number;
  limit: number;
}): JSX.Element {
  // noDays == 0：灰色文字「尚無無新影片記錄」
  // noDays > 0 && noDays < limit - 1：正常文字
  // noDays >= limit - 1：橘色警示
}
```

---

### api/public.ts 使用（step12 已建立）

本 step 直接使用 step12 已建立的函式：
- `getPublicSubscriptions(email: string)`
- `deletePublicSubscription(id: string, email: string)`

---

### 導覽列連結

`AddSubscriptionPage` 的成功訊息區塊已有「查看我的訂閱」連結（step12），指向 `/my-subscriptions`。

頁面也可在簡易頁首加入「訂閱新頻道」連結，指向 `/`。

---

## 驗收標準

- [ ] 直接存取 `/my-subscriptions`（未登入）可正常顯示頁面
- [ ] 輸入有效 email 並查詢，正確顯示訂閱清單
- [ ] 每筆訂閱顯示：頻道名稱、發送時間（本地時間）、語速、建立時間、無新影片計數
- [ ] `no_new_video_days = 0` 時顯示「尚無無新影片記錄」
- [ ] `no_new_video_days > 0` 時顯示「連續無新影片：N 天 / 設定上限：M 天」
- [ ] 取消訂閱確認後呼叫 `DELETE /public/subscriptions/{id}?email={email}`
- [ ] 取消成功後訂閱從清單消失
- [ ] 無訂閱時顯示「此 Email 尚未訂閱任何頻道」
- [ ] `npm run build` 無 TypeScript 錯誤

---

## 工作分派

### 本 Step 指派
- **Coder B**（前端軌道）：可與 step12 同時進行，或在 step12 完成後接手

### 平行協作
- **Coder A** 同時執行 step11（後端）
- step14 可與本 step 同時由任一 Coder 接手

---

## 注意事項與限制

- `send_time` 與 `created_at` 的時區換算複用 `utils/timezone.ts` 中已有的 `utcTimeToLocal` 與 `formatUtcTimestamp`
- 查詢時不儲存 email 至 localStorage（避免隱私疑慮）；用戶離開頁面重新進入需重新輸入
- `window.confirm` 在行動裝置體驗不佳，若有時間可改為 inline 確認 UI，否則先用 `window.confirm`
- 頁面無需 `Layout` 包裝（無導覽列），獨立公開頁面風格
- 所有元件必須包含繁體中文函式級註解
- TypeScript 嚴格模式，禁止 `any` 型別
