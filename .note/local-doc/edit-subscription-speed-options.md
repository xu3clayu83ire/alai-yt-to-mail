# EditSubscriptionPage 語速選項與 AddSubscriptionPage 不一致

**日期**：2026-05-03  
**類型**：問題排除

---

## 發生了什麼

`AddSubscriptionPage.tsx` 提供 6 個語速選項：0.5、0.75、0.85、1.0、1.5、2.0。  
`EditSubscriptionPage.tsx` 只有 4 個：0.5、1.0、1.5、2.0，缺少 0.75 和 0.85。

實際效果：使用者新增訂閱時可以選 0.75x 或 0.85x，但編輯同一筆訂閱時這兩個選項消失，原本的值也無法正確顯示（因為 Zod schema 未包含這兩個值，驗證會失敗）。

## 根本原因

兩個頁面是分開撰寫的，語速選項清單在各自的 Zod schema 和 Select 元素中重複定義，新增選項時只更新了 Add 頁面，Edit 頁面被遺漏。沒有共用的常數或型別來確保兩者同步。

## 解法

在 `yt-to-mail/frontend/src/pages/EditSubscriptionPage.tsx` 進行兩處修改：

**Zod schema 更新**，補齊所有六個選項：

```typescript
audio_speed: z.enum(['0.5', '0.75', '0.85', '1.0', '1.5', '2.0'])
```

**Select 選單補齊兩個 option**：

```tsx
<option value="0.75">0.75x</option>
<option value="0.85">0.85x</option>
```

## 風險與注意事項

- 根本問題未解決：語速選項仍在兩個頁面各自重複定義。若未來再次新增語速（例如 1.25x），同樣容易再次漏改 Edit 頁面。
- 改善方向：將語速選項抽取為共用常數（例如 `constants/audioSpeed.ts`），兩個頁面都從該常數引用，可從根本避免不一致。

## 參考資料

- 相關檔案：`yt-to-mail/frontend/src/pages/AddSubscriptionPage.tsx`
- 相關檔案：`yt-to-mail/frontend/src/pages/EditSubscriptionPage.tsx`
