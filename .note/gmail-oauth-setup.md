# Gmail OAuth 授權設定指南

## 為什麼需要這個步驟？

`yt-to-mail` 需要以你的名義自動寄信，但 Google 不允許程式直接用帳號密碼登入 Gmail。  
必須走 **OAuth 2.0** 流程：你親自在瀏覽器點「允許」，Google 才會發給程式一張「通行證」（token.json）。  
往後程式每次寄信都用這張通行證，**不需要再開瀏覽器**，過期時也會自動更新。

---

## 前置準備：Google Cloud Console 設定

這些步驟只需要做一次。

### 1. 建立專案並啟用 Gmail API

1. 前往 [Google Cloud Console](https://console.cloud.google.com)
2. 點右上角專案選單 → **新增專案**，命名為 `yt-to-mail`
3. 左側選單 → **APIs & Services** → **程式庫**
4. 搜尋 `Gmail API` → 點進去 → 點 **啟用**

### 2. 設定 OAuth 同意畫面

1. 左側選單 → **APIs & Services** → **OAuth 同意畫面**
2. User Type 選 **外部** → 點 **建立**
3. 填入應用程式名稱（例如 `yt-to-mail`）、你的 Email → 儲存並繼續
4. Scopes 頁面直接按 **儲存並繼續**
5. **Test users** 區塊 → 點 **+ Add users**
6. 填入你的 Gmail：`prostyliu@gmail.com` → 儲存

> **為什麼要加 Test users？**  
> 應用程式未經 Google 正式審核前處於「測試模式」，只有被列為測試使用者的帳號才能完成授權。  
> 自己用不需要送審，加自己的帳號即可。

### 3. 建立 OAuth 2.0 憑證

1. 左側選單 → **APIs & Services** → **憑證**
2. 點上方 **+ 建立憑證** → **OAuth 用戶端 ID**
3. 應用程式類型選 **桌面應用程式**
4. 名稱隨意填（例如 `yt-to-mail-desktop`）→ 點 **建立**
5. 點 **下載 JSON**
6. 將下載的檔案重新命名為 `google_credentials_gmail.json`
7. 放到 `yt-to-mail/.source/` 目錄下

---

## 執行一次性授權

確認 `.env` 已填好以下兩個路徑：

```
GMAIL_CREDENTIALS_PATH=.source/google_credentials_gmail.json
GMAIL_TOKEN_PATH=.source/gmail_token.json
```

在 `yt-to-mail/` 目錄下執行：

```powershell
C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe auth_gmail.py
```

**流程：**
1. 瀏覽器自動開啟 Google 授權畫面
2. 選擇 `prostyliu@gmail.com`
3. 看到「yt-to-mail 想要存取你的 Google 帳戶」→ 點 **允許**
4. 終端機印出授權完成訊息與 token JSON 內容

授權完成後會產生 `.source/gmail_token.json`。

---

## 將 token 設定到 GitHub Secrets

GitHub Actions 執行時沒有辦法開瀏覽器授權，所以要把 token 預先存到 Secrets。

1. 前往 repo 的 Secrets 設定頁：  
   `https://github.com/xu3clayu83ire/alai-yt-to-mail/settings/secrets/actions`
2. 點 **New repository secret**
3. Name 填：`GMAIL_TOKEN_JSON`
4. Value 貼上 `auth_gmail.py` 執行後印出的那段 JSON（終端機 `---` 線以下的內容）
5. 點 **Add secret**

> **為什麼不直接把 token.json 推上 GitHub？**  
> token.json 等同於你的 Gmail 登入授權，一旦公開任何人都能以你的名義寄信。  
> 存到 GitHub Secrets 才是安全的做法，Secrets 是加密儲存的，程式碼裡看不到。

---

## token 過期怎麼辦？

Google 的 refresh token 通常不會過期（除非超過 6 個月沒有使用，或你在 Google Cloud Console 手動撤銷）。  
若某天 GitHub Actions 突然寄信失敗並顯示授權錯誤，重新執行 `auth_gmail.py` 再更新 `GMAIL_TOKEN_JSON` Secret 即可。

---

## 檔案說明

| 檔案 | 用途 | 是否可公開 |
|------|------|----------|
| `google_credentials_gmail.json` | OAuth 用戶端設定（從 Google Cloud 下載） | ❌ 不可 |
| `gmail_token.json` | 授權後產生的通行證 | ❌ 絕對不可 |
| `auth_gmail.py` | 一次性授權腳本 | ✅ 可以 |

> `.source/` 整個目錄已加入 `.gitignore`，不會被推上 GitHub。
