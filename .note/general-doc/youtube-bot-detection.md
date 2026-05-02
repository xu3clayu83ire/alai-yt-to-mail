# YouTube Bot 偵測導致下載失敗

**日期**：2026-05-01  
**類型**：問題排除

---

## 發生了什麼

GitHub Actions 執行 yt-dlp 下載 YouTube Shorts 時，全數失敗：

```
ERROR: [youtube] 4EL03MQgOg4: Sign in to confirm you're not a bot.
Use --cookies-from-browser or --cookies for the authentication.
See https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
for how to manually pass cookies.
```

本地端執行正常，僅在 GitHub Actions 上發生。

## 根本原因

GitHub Actions 使用 Microsoft Azure 資料中心的 IP。YouTube 會識別來自已知雲端 IP 範圍的請求，判定為自動化爬蟲，要求用戶登入後才能繼續。  
yt-dlp 沒有儲存任何登入狀態，因此被擋下。

補充：YouTube 已停止支援帳號密碼直接登入，無法透過在程式碼中填入帳密來繞過。

## 解法

匯出本機瀏覽器的 YouTube cookies，注入到 GitHub Actions 執行環境：

1. 安裝 Chrome 擴充功能 **Get cookies.txt LOCALLY**
2. 在已登入 YouTube 的狀態下匯出 `youtube.com_cookies.txt`
3. 將檔案內容存入 GitHub Secret：`YOUTUBE_COOKIES`
4. Workflow 執行時將 Secret 寫入 `.source/youtube_cookies.txt`
5. yt-dlp 設定加入 `cookiefile` 參數：

```python
cookies_path = os.getenv("YOUTUBE_COOKIES_PATH")
if cookies_path and Path(cookies_path).exists():
    ydl_opts["cookiefile"] = cookies_path
```

## 風險與注意事項

- **Cookies 有效期約 1〜2 年**，以下情況會提早失效：
  - 手動登出 YouTube
  - Google 帳號安全設定撤銷所有裝置登入
  - Google 偵測到異常活動
- 失效症狀：Actions 再次出現 `Sign in to confirm you're not a bot`
- 處理方式：重新匯出 cookies，更新 `YOUTUBE_COOKIES` Secret
- cookies 內容等同登入憑證，**絕對不能公開**

## 後續問題：web_creator client 需要 GVS PO Token

切換 player client 為 `web_creator` 後，出現新警告：

```
WARNING: web_creator client https formats require a GVS PO Token which was not provided.
WARNING: Only images are available for download.
ERROR: Requested format is not available.
```

**原因**：YouTube 的 `web_creator` client 需要額外的 GVS PO Token（Proof of Origin Token）才能取得影片格式，沒有 Token 時只剩靜態圖片可下載。

**解法**：改用 `ios` / `android` client，這兩個 client 不需要 PO Token，對 Shorts 支援完整：

```python
ydl_opts["extractor_args"] = {"youtube": {"player_client": ["ios", "android"]}}
```

## 終極結論：Azure IP 被全面封鎖

Azure 資料中心 IP 被 YouTube 全面封鎖，不管任何 client 或 cookies 組合都無效。  
**根本解法：改用家用 IP（本機執行）**，家用 IP 不在封鎖名單內。

## 參考資料

- [yt-dlp FAQ: How do I pass cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [yt-dlp: Exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
