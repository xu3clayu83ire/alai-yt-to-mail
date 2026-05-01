# yt-to-mail — Step 5：主程式整合與 GitHub Actions 部署

**負責 Agent**：cdk-coder  
**驗證 Agent**：cdk-tester  
**依賴**：Steps 1-4 完成

---

## 目標

整合所有模組為完整的主程式，並部署至 GitHub Actions 每日自動執行。

---

## 技術規格

### main.py — 主程式流程

```python
def main():
    # 1. 初始化 DB
    # 2. 取得頻道最新 Shorts 清單
    # 3. 過濾已處理影片
    # 4. 對每部未處理影片：
    #    a. 下載音訊
    #    b. 轉錄文字稿
    #    c. 寄送郵件
    #    d. 標記 DB 為已完成
    #    e. 清理暫存音訊檔
    # 5. 輸出執行摘要 log
```

### GitHub Actions Workflow（.github/workflows/daily.yml）

```yaml
name: Daily YouTube to Mail

on:
  schedule:
    - cron: '0 0 * * *'   # 每天 UTC 00:00（台灣 08:00）
  workflow_dispatch:        # 允許手動觸發

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r yt-to-mail/requirements.txt
      - name: Run yt-to-mail
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
          GMAIL_TOKEN_JSON: ${{ secrets.GMAIL_TOKEN_JSON }}
        run: python yt-to-mail/src/main.py
```

### GitHub Secrets 設定清單

| Secret 名稱 | 值來源 |
|-------------|--------|
| `YOUTUBE_API_KEY` | yt-to-mail_v1.md 中的 API Key |
| `OPENAI_API_KEY` | yt-to-mail_v1.md 中的 OpenAI Key |
| `RECIPIENT_EMAIL` | prostyliu@gmail.com |
| `GMAIL_TOKEN_JSON` | 本地執行授權後取得的 token.json 序列化內容 |

---

## 驗收條件

- [ ] 本地 `python yt-to-mail/src/main.py` 完整執行成功
- [ ] 收到測試郵件（含文字稿與音訊附件）
- [ ] GitHub Actions workflow 手動觸發成功
- [ ] Secrets 正確設定，無機密資訊硬編碼在程式碼中
