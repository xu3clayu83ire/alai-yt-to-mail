# yt-to-mail-step7：Phase 2 — 本機排程整合

## 功能名稱

本機排程處理器：DynamoDB 查詢 + yt-dlp + Whisper + Gmail 寄信

---

## 目標

在本機（Windows）建立每分鐘自動執行的排程腳本，負責：
1. 從 DynamoDB 查詢當分鐘到期的訂閱
2. 對每個訂閱執行：下載 YouTube 短影音 → Whisper 轉錄 → 英文判斷 → Gmail 寄信
3. 將執行結果（成功/失敗/跳過）寫回 DynamoDB history 表

本機僅做 outbound 連線，不對外暴露任何 port，安全性高。電腦關機時停止處理屬已知風險，原型階段可接受。

---

## 技術規格

### 執行環境

- 作業系統：Windows 11（使用 Windows 工作排程器）
- Python 版本：3.12
- 觸發頻率：每分鐘一次
- 執行模式：同步、循序處理（原型階段不需並行）

### AWS 憑證設定

- 建立專用 IAM User：`yt-to-mail-scheduler`
- 憑證類型：Access Key（本機 `aws configure` 設定）
- Profile 名稱：`yt-to-mail`（或 default，視環境而定）

### IAM User 最小權限 Policy

**Policy 名稱**：`yt-to-mail-scheduler-policy`

允許的操作與資源：
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadSubscriptions",
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:GetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:<region>:<account>:table/yt-to-mail-subscriptions",
        "arn:aws:dynamodb:<region>:<account>:table/yt-to-mail-subscriptions/index/*"
      ]
    },
    {
      "Sid": "WriteReadHistory",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:<region>:<account>:table/yt-to-mail-history"
      ]
    }
  ]
}
```

**禁止存取**：`yt-to-mail-users` 表（本機排程器不需要用戶認證資訊）

---

### 本機腳本目錄結構

```
scheduler/
  run.py                  # 主程式入口，Windows 工作排程器呼叫此檔
  config.py               # 設定讀取（AWS region、DynamoDB 表名、Gmail 設定）
  dynamo_reader.py        # 查詢 DynamoDB 訂閱資料
  processor.py            # 核心處理流程（下載→轉錄→判斷→寄信）
  history_writer.py       # 寫回 DynamoDB history 表
  gmail_sender.py         # Gmail API 寄信（沿用 v1 邏輯）
  requirements.txt
  .env                    # 本機環境變數（不納入版控）
  .env.example            # 環境變數範本（納入版控）
  logs/
    scheduler.log         # 執行日誌（rotate 策略：每日一份，保留 7 天）
```

---

### 設定檔規格（config.py）

從環境變數（.env 檔）讀取以下設定：

| 變數名稱 | 說明 | 範例值 |
|---|---|---|
| `AWS_REGION` | DynamoDB 所在 AWS Region | `ap-northeast-1` |
| `SUBSCRIPTIONS_TABLE` | subscriptions 表名 | `yt-to-mail-subscriptions` |
| `HISTORY_TABLE` | history 表名 | `yt-to-mail-history` |
| `GMAIL_CREDENTIALS_FILE` | Gmail API credentials.json 路徑 | `C:\path\to\credentials.json` |
| `GMAIL_TOKEN_FILE` | Gmail API token.json 路徑 | `C:\path\to\token.json` |
| `GMAIL_SENDER` | 寄件人 Email | `sender@gmail.com` |
| `WHISPER_MODEL` | Whisper 模型大小 | `base` |
| `YTDLP_OUTPUT_DIR` | yt-dlp 暫存目錄 | `C:\temp\yt-to-mail` |

---

### DynamoDB 查詢邏輯（dynamo_reader.py）

**查詢目標**：取得所有 `is_active=true` 且 `send_time` 等於當前 UTC 分鐘的訂閱

**查詢步驟**：

1. 取得當前 UTC 時間，格式化為 `HH:MM`（例如 `14:30`）
2. 對 `yt-to-mail-subscriptions` 表執行 Scan（原型階段訂閱數少，Scan 可接受）
3. 篩選條件：
   - `is_active = true`
   - `send_time = <當前 UTC HH:MM>`
4. 回傳符合條件的訂閱清單

**注意**：send_time 儲存的是 UTC 時間，本機腳本使用 `datetime.utcnow()` 取得 UTC 當前分鐘進行比對，避免時差問題。

---

### 核心處理流程（processor.py）

對每個查詢到的訂閱，依序執行以下步驟：

**Step 1：取得頻道候選影片清單**

使用 yt-dlp 的 `--flat-playlist` 模式取得頻道最新 `MAX_CANDIDATE_VIDEOS`（預設 10）支影片的元資料清單：
```python
MAX_CANDIDATE_VIDEOS = 10

ydl_opts = {
    "quiet": True,
    "extract_flat": True,
    "playlist_items": f"1-{MAX_CANDIDATE_VIDEOS}",  # 取最新 N 支
}
```

- 過濾掉 ID 以 `UC` 開頭的條目（channel ID，非真實影片）
- 若頻道無影片或存取受限，跳過此訂閱（不寫 history，`status='no_video'`）

**Step 2：找出第一支未寄過的影片**

一次 Scan 取得此訂閱的所有已寄 video_id，再從候選清單中由新到舊找第一支未寄過的影片：

```python
# 一次 Scan 取回所有已寄 video_id（原型階段 history 數量少，Scan 可接受）
sent_video_ids = history_writer.get_sent_video_ids(subscription_id)
# FilterExpression: subscription_id == X AND status == "done"
# ProjectionExpression: video_id（只取 video_id，節省讀取量）

video_info = next(
    (e for e in candidate_videos if e.get("id", "") not in sent_video_ids),
    None,
)
```

- 若找到未寄過的影片：繼續後續下載流程
- 若候選清單中全部都已寄過：
  - 呼叫 `send_no_new_video_email()` 通知收件人此頻道近期沒有新影片
  - 回傳 `status='skipped_duplicate'`，**不寫入** history
- 若 Scan 發生例外：保守回傳空 set（允許繼續處理），記錄 warning log

> **效能說明**：`get_sent_video_ids` 使用 Scan 讀取整張 history 表再過濾，費用與延遲取決於表的總資料量。原型階段紀錄數量少（數百筆），Scan 耗時 <100ms 且費用幾乎為零，可接受。
>
> **未來優化（規模擴大時）**：在 history 表新增 GSI：
> - Partition Key：`subscription_id`（String）
> - Sort Key：`status`（String）
>
> 改用 `Query` 代替 `Scan`，只讀取該訂閱的紀錄，讀取量從 O(全表) 降為 O(單一訂閱紀錄數)。

**Step 3：下載音訊（僅前 60 秒）**

使用 `download_ranges` 限制只下載前 60 秒，不受影片總時長限制，節省頻寬：
```python
ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": f"{output_dir}/{video_id}.%(ext)s",
    "quiet": True,
    "download_ranges": yt_dlp.utils.download_range_func(None, [(0, 60)]),
    "force_keyframes_at_cuts": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3"
    }]
}
```

暫存路徑：`YTDLP_OUTPUT_DIR/{video_id}.mp3`

**Step 4：音速調整（可選）**

若 `audio_speed != 1.0`，使用 FFmpeg 調整播放速度：
```bash
ffmpeg -i input.mp3 -filter:a "atempo={audio_speed}" output_speed.mp3
```
`audio_speed` 有效範圍：0.5, 0.75, 0.85, 1.0, 1.5, 2.0

**Step 5：Whisper 語音轉文字**

```python
import whisper

model = whisper.load_model(WHISPER_MODEL)  # 例如 "base"
result = model.transcribe(audio_file, fp16=False)
language = result["language"]
text = result["text"]
```

**Step 6：英文判斷**

- 若 `language != "en"`：
  - 寫入 history，`status = "skipped_language"`
  - 停止此訂閱的後續步驟
  - 不寄信

**Step 7：Gmail 寄信**

寄信內容：
- 主旨：`[yt-to-mail] {video_title}`
- 內文（純文字 + HTML 雙版本）：
  ```
  頻道：{channel_name}
  影片：{video_title}
  YouTube 連結：https://www.youtube.com/watch?v={video_id}

  文字稿：
  {whisper_text}
  ```
- 附件：調整語速後的 mp3 檔案（若 `audio_speed == 1.0` 則附原始音訊）
- 收件人：訂閱的 `recipient_email`

**Step 8：寫回 history**

執行結果統一寫入 `yt-to-mail-history` 表：
```python
{
  "id": uuid4(),
  "user_id": subscription["user_id"],
  "subscription_id": subscription["id"],
  "video_id": video_id,
  "video_title": video_title,
  "sent_at": datetime.utcnow().isoformat() + "Z",
  "status": "done"  # 或 "failed" 或 "skipped_language"
}
```

失敗時額外寫入：
```python
{
  "error_message": str(exception)  # 截斷至 500 字元
}
```

**Step 9：暫存檔清理**

處理完成（無論成功或失敗）後，刪除 `YTDLP_OUTPUT_DIR` 中此次下載的音訊檔案。

---

### 錯誤處理規格

| 錯誤情境 | 處理方式 | history status |
|---|---|---|
| yt-dlp 下載失敗 | 記錄錯誤，寫回 history | `failed` |
| Whisper 轉錄失敗 | 記錄錯誤，寫回 history | `failed` |
| 非英文影片 | 跳過，不寄信，寫回 history | `skipped_language` |
| Gmail 寄信失敗 | 記錄錯誤，寫回 history | `failed` |
| DynamoDB 寫入失敗 | 僅記錄本機 log，不重試 | （無 history 記錄） |
| 頻道無影片或無法存取 | 靜默跳過，不寫 history | — |
| 候選清單（最新 10 支）均已寄過 | 寄送無新影片通知信，不寫 history | `skipped_duplicate`（不入庫） |

每個訂閱的處理失敗不影響後續訂閱的執行（個別 try/except 包裝）。

---

### 日誌規格（logs/scheduler.log）

每次執行記錄：
```
[2026-05-01 14:00:01 UTC] 開始執行，當前 UTC 時間：14:00
[2026-05-01 14:00:01 UTC] 查詢到 3 個訂閱
[2026-05-01 14:00:05 UTC] [sub:uuid-1] 處理中 - 頻道: @channel1
[2026-05-01 14:00:45 UTC] [sub:uuid-1] 完成 - video_id: abc123, status: done
[2026-05-01 14:00:46 UTC] [sub:uuid-2] 處理中 - 頻道: @channel2
[2026-05-01 14:01:10 UTC] [sub:uuid-2] 跳過 - status: skipped_language (detected: ja)
[2026-05-01 14:01:10 UTC] 執行完成，耗時 69 秒
```

日誌 rotate：每日一份（`scheduler_2026-05-01.log`），保留 7 天，使用 Python `logging.handlers.TimedRotatingFileHandler`。

---

### Windows 工作排程器設定

使用 PowerShell 建立排程工作：

```powershell
# 建立每分鐘執行一次的排程工作
$action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "D:\12_Claude_Assistant\yt-to-mail\scheduler\run.py" `
    -WorkingDirectory "D:\12_Claude_Assistant\yt-to-mail\scheduler"

$trigger = New-ScheduledTaskTrigger `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -Once `
    -At (Get-Date)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "yt-to-mail-scheduler" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "yt-to-mail 本機排程處理器" `
    -RunLevel Highest
```

**重要設定說明**：
- `MultipleInstances IgnoreNew`：若上次執行未完成，跳過本次觸發（防止重疊執行）
- `ExecutionTimeLimit 5 分鐘`：避免異常時佔用資源超過 5 分鐘
- `RunLevel Highest`：以最高權限執行（避免存取憑證檔案時的權限問題）

---

### 必要套件（requirements.txt）

```
boto3==1.34.0
python-dotenv==1.0.0
openai-whisper==20231117
yt-dlp==2024.11.18
google-api-python-client==2.100.0
google-auth-oauthlib==1.1.0
```

外部依賴（需另外安裝）：
- FFmpeg：需加入 PATH 環境變數
- Python 3.12

---

## 實作步驟（供 cdk-coder 執行）

- Step 1：在 CDK Stack 中建立 IAM User `yt-to-mail-scheduler` 及對應 Policy（subscriptions 讀 + history 寫）
- Step 2：建立 IAM Access Key，輸出至 CDK Output 供本機設定使用
- Step 3：建立 `scheduler/` 目錄及 `requirements.txt`
- Step 4：實作 `config.py`（使用 python-dotenv 讀取 .env，包含所有設定項目）
- Step 5：實作 `dynamo_reader.py`（UTC 時間比對，Scan subscriptions 表）
- Step 6：實作 `processor.py`（yt-dlp 取清單 → 篩選 ≤60s → 下載 → Whisper → 英文判斷 → 語速調整）
- Step 7：實作 `gmail_sender.py`（主旨格式、文字稿內文、mp3 附件）
- Step 8：實作 `history_writer.py`（PutItem 寫回 history 表，含 error_message 處理）
- Step 9：實作 `run.py`（主迴圈，讀取訂閱清單，循序呼叫 processor，個別 try/except）
- Step 10：建立 `.env.example` 範本檔案
- Step 11：記錄 Windows 工作排程器設定指令於 `scheduler/README.md`

---

## 驗收標準

- [ ] CDK 成功建立 IAM User `yt-to-mail-scheduler` 及 Access Key 輸出
- [ ] IAM Policy 僅允許 subscriptions 讀取與 history 寫入，無 users 表權限
- [ ] `run.py` 執行時，正確取得當前 UTC `HH:MM` 並查詢 DynamoDB
- [ ] 模擬訂閱到期場景，`processor.py` 能完整執行下載→轉錄→寄信流程
- [ ] 非英文影片（Whisper 偵測 language != en）寫入 `status=skipped_language`，不寄信
- [ ] yt-dlp 或 Whisper 異常時，寫入 `status=failed` 並包含 error_message
- [ ] 個別訂閱失敗不中斷其他訂閱的處理
- [ ] 暫存音訊檔在處理完成後被刪除
- [ ] Windows 工作排程器每分鐘觸發一次，重疊執行時跳過（IgnoreNew）
- [ ] 執行日誌寫入 `logs/scheduler.log`，每日 rotate

---

## 注意事項與限制

- 本機腳本不得存取 `yt-to-mail-users` 表（最小權限原則）
- `.env` 檔案不得納入版控（已加入 .gitignore）
- `GMAIL_CREDENTIALS_FILE` 與 `GMAIL_TOKEN_FILE` 為絕對路徑
- Whisper `fp16=False` 設定是因為 CPU 推論不支援 fp16
- yt-dlp 取影片清單時若頻道設有存取限制，直接記錄 failed 並跳過
- audio_speed 調整使用 FFmpeg `atempo` filter，若值不在 [0.5, 2.0] 範圍 FFmpeg 會異常，需在 processor.py 做 clamp 處理
- 所有函式必須包含繁體中文函式級註解
