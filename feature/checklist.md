# 功能驗收清單

---

## 功能：yt-to-mail

### 程式品質
- [ ] `mypy src/` 無型別錯誤
- [ ] `pytest tests/` 全數通過
- [ ] 測試覆蓋率 ≥ 80%（核心模組）
- [ ] 無硬編碼的 API Key 或密鑰
- [ ] 所有函式具備繁體中文函式級註解

### 功能正確性
- [ ] YouTube Shorts 清單抓取正確（含當天最新影片）
- [ ] 已處理影片不重複下載（SQLite 去重複有效）
- [ ] 音訊成功下載為 mp3 格式
- [ ] Whisper 語音轉文字結果可讀
- [ ] 郵件成功寄達 prostyliu@gmail.com
- [ ] 郵件含正確主旨格式：`[yt-to-mail] {影片標題} — {日期}`
- [ ] 郵件含完整文字稿內文
- [ ] 音訊附件正確附加（< 25MB）

### 安全性
- [ ] 所有機密資訊透過環境變數或 GitHub Secrets 管理
- [ ] `.env` 已加入 `.gitignore`
- [ ] `credentials.json` 與 `token.json` 已加入 `.gitignore`
- [ ] `.source/` 目錄已加入 `.gitignore`

### 部署鏈路
- [ ] `pip install -r requirements.txt` 成功
- [ ] 本地 `python src/main.py` 完整執行成功
- [ ] GitHub Actions workflow 存在且語法正確
- [ ] GitHub Actions 手動觸發（workflow_dispatch）成功
- [ ] GitHub Actions 排程觸發時間正確（台灣時間每天 08:00）

### 錯誤處理
- [ ] API 失敗時有重試機制
- [ ] 下載失敗時標記 DB status='failed'，不影響其他影片
- [ ] 音訊超過 25MB 時只寄文字稿並有說明
- [ ] 缺少環境變數時有清楚錯誤訊息

### 文件完整性
- [ ] README.md 含安裝與執行說明
- [ ] .env.example 完整且有說明
- [ ] GitHub Secrets 設定說明文件存在
