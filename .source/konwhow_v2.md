## yt-to-mail 是一個 YouTube 頻道訂閱通知服務，運作流程如下：

1. 用戶填寫訂閱表單，指定：

- YouTube 頻道 URL
- 收件 Email
- 每日寄送時間（UTC）
- 音訊播放速度（可選）

2. Windows 工作排程器每分鐘執行 run.py，找出當前分鐘到期的訂閱

3. 對每個訂閱執行：

- 用 yt-dlp 抓頻道最新 10 支影片候選清單
- 找出第一支尚未寄過的影片
- 下載前 60 秒音訊（mp3）
- 若設定速度 ≠ 1.0，用 FFmpeg 調整速度
- 用 Whisper 做語音轉文字
- 若非英文，記錄 skipped_language 跳過
- 用 Gmail 寄送包含逐字稿 + mp3 附件的 Email
- 寫入 DynamoDB history 記錄


簡單說：訂閱 YouTube 頻道 → 每天自動收到該頻道新影片的英文逐字稿 + 60 秒音訊摘要 - Email，目標是讓用戶每天可以練習一小段英文。