# yt-to-mail｜開發計畫書

版本 1.0　|　2026 年 5 月

---

## 1. 專案概述

**yt-to-mail** 自動追蹤指定 YouTube 頻道，每天將新影片的音訊下載並轉成文字稿，透過 Gmail 自動寄送至指定信箱，無需人工介入。

核心特點：
- 每日定時執行，自動判斷哪些影片尚未處理
- 音訊與文字稿同步寄出，方便隨時回顧
- 以 SQLite 記錄處理歷史，確保不重複下載
- 部署於 GitHub Actions，零成本雲端自動化

---

## 2. 所需 API 與金鑰（需由您提供）

| API 名稱 | 申請平台 | 費用 | 用途 |
|----------|----------|------|------|
| YouTube Data API v3 | Google Cloud Console | 免費 | 抓取頻道影片清單 |
| Gmail API | Google Cloud Console | 免費 | 每日自動寄送郵件 |
| OpenAI Whisper API | OpenAI Platform | $0.006/分鐘（可選） | 語音轉文字（可改用本地版免費） |

### 2.1 YouTube Data API v3

1. 前往 [Google Cloud Console](https://console.cloud.google.com)
2. 建立新專案，命名為「yt-to-mail」
3. 啟用「YouTube Data API v3」
4. 建立 API 金鑰（Credentials → API Key）
5. **提供：API Key 字串**

### 2.2 Gmail API

1. 在同一個 Google Cloud Console 專案中，啟用「Gmail API」
2. 建立 OAuth 2.0 用戶端 ID（類型選「桌面應用程式」）
3. 下載 `credentials.json`
4. 首次執行時用瀏覽器完成授權，系統會自動產生 `token.json`
5. **提供：`credentials.json` 檔案**

### 2.3 OpenAI Whisper API（可選）

若選擇本地 Whisper，此步驟略過（完全免費，但雲端伺服器需 4GB RAM 以上）。

1. 前往 [platform.openai.com](https://platform.openai.com)
2. 建立 API Key
3. **提供：`sk-` 開頭的 API Key 字串**

---

## 3. 技術架構

| 元件 | 工具 | 說明 |
|------|------|------|
| 語言 | Python 3.11+ | 主要開發語言 |
| 影片下載 | yt-dlp | 從 YouTube 下載純音訊（mp3） |
| 語音轉文字 | OpenAI Whisper | 本地或 API 兩種模式皆支援 |
| 音訊處理 | ffmpeg | 音訊格式轉換 |
| 去重複 | SQLite | 記錄已處理影片 ID |
| 排程 | GitHub Actions | 每日定時觸發，免費額度充足 |
| 寄信 | Gmail API | OAuth 2.0 授權自動寄信 |

---

## 4. 系統流程

```
GitHub Actions 定時觸發（每天早上 8:00）
  ↓
YouTube Data API 取得頻道最新影片清單
  ↓
比對 SQLite → 篩選未處理影片
  ↓
yt-dlp 下載音訊（mp3）
  ↓
Whisper 轉成文字稿
  ↓
Gmail API 寄出（標題 + 文字稿 + 音檔附件）
  ↓
記錄至 SQLite，標記為已完成
```

---

## 5. 預估開發時程

| 階段 | 項目 | 時程 |
|------|------|------|
| Phase 1 | 環境建置與 API 設定 | 1 天 |
| Phase 2 | 影片下載與去重複模組 | 2 天 |
| Phase 3 | 語音轉文字模組 | 2 天 |
| Phase 4 | 寄信模組 | 1 天 |
| Phase 5 | GitHub Actions 排程 | 1 天 |
| Phase 6 | 測試與上線 | 1 天 |

總計：**約 8 個工作天**

---

## 6. 費用估算

以每天處理 1 部影片（平均 30 分鐘）為基準：

- YouTube Data API：**免費**（每天約用 1–5 units）
- Whisper 本地版：**完全免費**
- Whisper API 版：每月約 NT$16–30（30 分 × 30 天 × $0.006/分）
- Gmail API：**免費**
- GitHub Actions：**免費**（每月 2,000 分鐘綽綽有餘）

建議初期使用本地 Whisper，有需要再切換 API 版本。

---

## 7. 開始前您需要準備的項目

- [x] YouTube Data API v3 金鑰
- [x] 要追蹤的 YouTube 頻道網址
- [x] Gmail API 的 `credentials.json`
- [x] 收件信箱地址
- [x] 決定 Whisper 模式（本地 or API）；若選 API 版，提供 OpenAI Key
- [x] GitHub 帳號（用於部署 yt-to-mail）
