# 開發進度追蹤

> **更新規則**：每完成一個步驟，AI 必須立即更新本文件，將對應項目標記為已完成。

---

## 功能：yt-to-mail（2026-05-01）

### 規格階段
- [x] prompt-architect 完成需求分析與技術規格
- [x] 建立 feature/yt-to-mail-step1.md（環境建置）
- [x] 建立 feature/yt-to-mail-step2.md（YouTube 抓取與下載）
- [x] 建立 feature/yt-to-mail-step3.md（語音轉文字）
- [x] 建立 feature/yt-to-mail-step4.md（Gmail 寄信）
- [x] 建立 feature/yt-to-mail-step5.md（整合與 GitHub Actions）
- [x] 更新 checklist.md 驗收項目

### Step 1：專案結構與環境建置 ✅
- [x] 建立 yt-to-mail/ 目錄結構
- [x] 建立 requirements.txt
- [x] 建立 .env.example
- [x] 實作 src/config.py
- [x] 實作 src/database.py（SQLite init + CRUD）
- [x] 建立 tests/test_database.py
- [x] 建立 tests/test_config.py
- [x] cdk-tester 驗證通過（7 tests passed）

### Step 2：YouTube 影片抓取與音訊下載 ✅
- [x] 實作 src/youtube.py（get_channel_id + get_latest_shorts）
- [x] 實作 src/downloader.py（download_audio）
- [x] 實作 database.py 去重複函式
- [x] 建立 tests/test_youtube.py（含 mock）
- [x] 建立 tests/test_downloader.py（含 mock）
- [x] cdk-tester 驗證通過（15 tests passed）

### Step 3：語音轉文字 ✅
- [x] 實作 src/transcriber.py（Whisper API + 重試邏輯）
- [x] 建立 tests/test_transcriber.py（含 mock）
- [x] cdk-tester 驗證通過（21 tests passed）

### Step 4：Gmail 寄信模組 ✅
- [x] 實作 src/mailer.py（OAuth 2.0 + 寄信 + 附件）
- [x] 建立 tests/test_mailer.py（含 mock）
- [x] cdk-tester 驗證通過（21 tests passed）

### Step 5：整合與部署
- [x] 實作 src/main.py（完整流程）
- [x] 建立 .github/workflows/daily.yml
- [ ] 建立 .env（填入真實 API Keys）
- [ ] Gmail OAuth 首次授權（取得 token.json）
- [ ] 本地端完整測試執行成功（收到測試郵件）
- [ ] GitHub Secrets 設定完成
- [ ] GitHub Actions 手動觸發成功

### 文件階段
- [ ] doc-master 更新 yt-to-mail/README.md
- [ ] doc-master 更新 CHANGELOG.md
