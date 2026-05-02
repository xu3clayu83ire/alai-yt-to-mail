# yt-to-mail 本機排程器

## 概述

本機排程器每分鐘查詢 DynamoDB 中到期的訂閱，並對每個訂閱執行：
1. yt-dlp 查詢頻道最新短影音（≤ 60 秒）
2. 下載音訊 → Whisper 語音轉文字
3. 語言判斷（僅處理英文影片）
4. Gmail 寄送逐字稿與 mp3 附件
5. 寫入 DynamoDB history 記錄執行結果

## 安裝需求

- Python 3.12
- FFmpeg（需加入 PATH 環境變數）
- AWS CLI（本機 `aws configure` 設定 yt-to-mail 憑證）

## 設定步驟

### 1. 安裝 Python 依賴套件

```powershell
cd D:\12_Claude_Assistant\yt-to-mail\scheduler
pip install -r requirements.txt
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env` 並填入實際值：

```powershell
Copy-Item .env.example .env
```

編輯 `.env` 填入以下設定：
- AWS Region 與 DynamoDB 表名
- Gmail API credentials.json 與 token.json 路徑
- Whisper 模型大小
- yt-dlp 暫存目錄

### 3. 設定 AWS 憑證

從 CDK Stack 的 Output 取得 Access Key ID 與 Secret Access Key，
然後設定 AWS 憑證（建議使用 named profile）：

```powershell
aws configure --profile yt-to-mail
# 輸入 Access Key ID、Secret Access Key、Region
```

或直接在 `.env` 中加入：
```
AWS_ACCESS_KEY_ID=<從 CDK Output 取得>
AWS_SECRET_ACCESS_KEY=<從 CDK Output 取得>
```

### 4. Gmail OAuth2 授權

首次執行前需先完成 Gmail OAuth2 授權（會開啟瀏覽器）：

```powershell
python run.py
```

授權完成後，token.json 會自動儲存，後續執行不需重新授權。

## Windows 工作排程器設定

使用以下 PowerShell 指令建立每分鐘執行一次的排程工作：

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
    -Description "yt-to-mail local scheduler" `
    -RunLevel Highest
```

### 重要設定說明

- `MultipleInstances IgnoreNew`：若上次執行未完成，跳過本次觸發（防止重疊執行）
- `ExecutionTimeLimit 5 分鐘`：避免異常時佔用資源超過 5 分鐘
- `RunLevel Highest`：以最高權限執行（避免存取憑證檔案時的權限問題）

### 管理排程工作

```powershell
# 查看排程工作狀態
Get-ScheduledTask -TaskName "yt-to-mail-scheduler"

# 手動觸發一次
Start-ScheduledTask -TaskName "yt-to-mail-scheduler"

# 停用排程工作
Disable-ScheduledTask -TaskName "yt-to-mail-scheduler"

# 刪除排程工作
Unregister-ScheduledTask -TaskName "yt-to-mail-scheduler" -Confirm:$false
```

## 日誌

執行日誌位於 `logs/scheduler.log`，每日自動 rotate，保留最近 7 天。

```powershell
# 查看最新日誌
Get-Content logs\scheduler.log -Tail 50
```

## 錯誤處理

| 錯誤情境 | 處理方式 | History Status |
|---|---|---|
| yt-dlp 下載失敗 | 記錄錯誤，寫 history | `failed` |
| Whisper 轉錄失敗 | 記錄錯誤，寫 history | `failed` |
| 非英文影片 | 跳過，不寄信 | `skipped_language` |
| Gmail 寄信失敗 | 記錄錯誤，寫 history | `failed` |
| DynamoDB 寫入失敗 | 僅記錄本機 log | （無 history） |
| 無符合影片 | 靜默跳過 | （無 history） |
