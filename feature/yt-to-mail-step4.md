# yt-to-mail — Step 4：Gmail 自動寄信模組

**負責 Agent**：cdk-coder  
**驗證 Agent**：cdk-tester  
**依賴**：Step 3 完成

---

## 目標

將音訊檔與文字稿透過 Gmail API 以 OAuth 2.0 自動寄送至指定信箱。

---

## 技術規格

### mailer.py

#### 函式：`send_email(video_info: VideoInfo, transcript: TranscriptResult, audio_path: str)`

**郵件格式**
- 主旨：`[yt-to-mail] {video_title} — {日期}`
- 正文（HTML）：
  ```
  📹 影片：{title}
  🔗 連結：https://youtube.com/watch?v={video_id}
  🗣️ 語言：{language}
  ⏱️ 時長：{duration}

  --- 文字稿 ---
  {transcript_text}
  ```
- 附件：`{video_id}.mp3`（若音訊檔 < 25MB，Gmail 附件限制）

#### Gmail OAuth 2.0 設定
- credentials 路徑：來自 `config.GMAIL_CREDENTIALS_PATH`
- token 快取路徑：來自 `config.GMAIL_TOKEN_PATH`
- Scope：`https://www.googleapis.com/auth/gmail.send`
- 首次執行時自動開啟瀏覽器授權（本地執行）
- GitHub Actions 環境：從 Secret 讀取序列化 token（不開瀏覽器）

#### 錯誤處理
- token 過期：自動 refresh
- 附件超過 25MB：只寄文字稿，郵件正文註明音訊過大

---

## 驗收條件

- [ ] 成功寄出含文字稿的測試郵件至 `prostyliu@gmail.com`
- [ ] 音訊附件正確附加（< 25MB）
- [ ] token refresh 正確運作
- [ ] `pytest tests/test_mailer.py` 通過（mock Gmail API）
