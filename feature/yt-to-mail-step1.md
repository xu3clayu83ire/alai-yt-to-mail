# yt-to-mail — Step 1：專案結構與環境建置

**負責 Agent**：cdk-coder  
**驗收 Agent**：cdk-tester（Python 版：mypy + pytest + 執行測試）  
**預估時程**：1 天

---

## 目標

建立可執行的 Python 專案骨架，確認所有依賴套件可正常安裝，SQLite 資料庫初始化成功。

---

## 技術規格

### 專案目錄結構

```
yt-to-mail/
  src/
    __init__.py
    config.py          # 從環境變數讀取設定
    database.py        # SQLite 初始化與 CRUD
    youtube.py         # YouTube Data API 模組（Step 2）
    downloader.py      # yt-dlp 音訊下載（Step 2）
    transcriber.py     # Whisper 語音轉文字（Step 3）
    mailer.py          # Gmail API 寄信（Step 4）
    main.py            # 主程式入口（Step 5 整合）
  tests/
    __init__.py
    test_database.py   # 資料庫單元測試
    test_config.py     # 設定讀取測試
  .github/
    workflows/
      daily.yml        # GitHub Actions（Step 5）
  .env.example         # 環境變數範本
  requirements.txt     # 依賴套件清單
  README.md
```

### 依賴套件（requirements.txt）

```
yt-dlp>=2024.1.0
openai>=1.0.0
google-api-python-client>=2.100.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.2.0
python-dotenv>=1.0.0
pytest>=8.0.0
mypy>=1.8.0
```

### 環境變數（.env.example）

```
YOUTUBE_API_KEY=your_youtube_api_key
YOUTUBE_CHANNEL_URL=https://www.youtube.com/@channel/shorts
OPENAI_API_KEY=sk-...
GMAIL_CREDENTIALS_PATH=.source/google_credentials_gmail.json
GMAIL_TOKEN_PATH=.source/gmail_token.json
RECIPIENT_EMAIL=your@email.com
DB_PATH=data/processed.db
```

### SQLite Schema（database.py）

```sql
CREATE TABLE IF NOT EXISTS processed_videos (
    video_id    TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status      TEXT DEFAULT 'done'   -- done | failed
);
```

### config.py 規格

- 使用 `python-dotenv` 從 `.env` 讀取所有環境變數
- 若必要環境變數缺失，拋出明確錯誤訊息，不使用預設值掩蓋問題

---

## 驗收條件

- [ ] `pip install -r requirements.txt` 成功
- [ ] `python -c "import src.config"` 無錯誤
- [ ] `python -c "from src.database import init_db; init_db()"` 成功建立 DB
- [ ] `pytest tests/` 全數通過
- [ ] `mypy src/` 無型別錯誤
