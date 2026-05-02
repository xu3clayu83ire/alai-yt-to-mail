# Gmail 顯示「寄件者未驗證」警告

**日期**：2026-05-03  
**類型**：問題排除

---

## 發生了什麼

透過 Gmail API 成功寄出郵件，但收件端收到信時，Gmail 介面顯示「寄件者未驗證」的安全警告橫幅。郵件內容正常，實際並未被攔截或退信。

## 根本原因

排查過程先排除了兩個常見誤判：

1. **From 欄位不一致**：`GMAIL_SENDER` 與 OAuth2 授權帳號相同，非此原因。
2. **SPF/DKIM 問題**：使用 Gmail API 發送時，Google 自動為信件加上 SPF/DKIM 簽章，非此原因。

真正原因：Google Cloud Console 中的 OAuth 應用程式處於 **Testing（測試中）** 狀態。Google 對所有透過未審核 OAuth App 發出的郵件一律加上安全警告，不論寄件者是否就是授權帳號本人。

## 解法

將 OAuth 應用程式狀態從 Testing 改為 In production：

1. 前往 [Google Cloud Console](https://console.cloud.google.com) → 選擇專案
2. 左側選單 → **APIs & Services** → **OAuth consent screen**
3. 找到 **Publishing status** 區塊 → 點擊 **Publish App**
4. 確認後狀態變為 `In production`

狀態改變後，透過此 OAuth App 發送的郵件不再顯示「寄件者未驗證」警告。

**為什麼可以直接發佈而不需要 Google 審核**：`gmail.send` 屬於 Gmail API 的非受限範圍（non-sensitive scope），個人或內部使用的應用程式不需要通過 Google 的完整 OAuth 審核流程，點擊 Publish App 即可直接生效。

## 風險與注意事項

- 發佈後任何 Google 帳號（非僅限 Test users 清單）都可以嘗試授權此應用程式。若應用程式的 OAuth 憑證外洩，風險範圍會比 Testing 狀態大。務必確保 credentials JSON 不進版本控制。
- 若未來使用到 **受限範圍（restricted/sensitive scope）**（例如讀取信件、管理聯絡人），就必須提交 Google 審核，且審核期間應用程式會回到受限狀態。目前 `gmail.send` 不在此列。
- 此設定是專案層級的，修改後無需重新產生 token 或更新任何環境變數。

## 參考資料

- [Google OAuth 2.0 Scopes for Gmail API](https://developers.google.com/gmail/api/auth/scopes)
- [Publishing status 說明](https://support.google.com/cloud/answer/10311615)
