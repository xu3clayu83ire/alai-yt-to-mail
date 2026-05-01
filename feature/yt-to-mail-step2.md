# yt-to-mail — Step 2：YouTube 影片抓取與音訊下載

**負責 Agent**：cdk-coder  
**驗證 Agent**：cdk-tester  
**依賴**：Step 1 完成

---

## 目標

從指定 YouTube 頻道取得最新 Shorts 影片清單，比對 SQLite 去重複後，下載尚未處理的影片音訊（mp3）。

---

## 技術規格

### youtube.py — YouTube Data API 模組

#### 函式：`get_channel_id(channel_url: str) -> str`
- 從頻道 URL 解析出 channel_id
- 使用 YouTube Data API v3 `channels.list` endpoint
- 若找不到則拋出 `ValueError`

#### 函式：`get_latest_shorts(channel_id: str, max_results: int = 10) -> list[VideoInfo]`
- 呼叫 `search.list` API，篩選 `videoDuration=short`（< 4 分鐘）
- 回傳 `VideoInfo` dataclass 清單

```python
@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel_id: str
    published_at: str
    duration_seconds: int
```

#### API 設定
- API Key：來自 `config.YOUTUBE_API_KEY`
- 每次呼叫最多取 `max_results=10` 筆
- 使用 `publishedAfter` 篩選昨天以後的影片（避免拉太多歷史）

### downloader.py — yt-dlp 音訊下載模組

#### 函式：`download_audio(video_id: str, output_dir: str) -> str`
- 使用 `yt-dlp` 下載指定 video_id 的音訊
- 輸出格式：mp3，bitrate 128kbps
- 輸出路徑：`{output_dir}/{video_id}.mp3`
- 回傳下載完成的檔案路徑
- 若下載失敗，拋出 `DownloadError`

#### yt-dlp 設定
```python
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '128',
    }],
    'outtmpl': f'{output_dir}/{video_id}.%(ext)s',
    'quiet': True,
}
```

### database.py 新增函式

#### `is_processed(video_id: str) -> bool`
- 查詢 `processed_videos` 表，回傳是否已處理

#### `mark_processed(video_id: str, title: str, channel_id: str, status: str = 'done')`
- 插入或更新處理紀錄

---

## 驗收條件

- [ ] `get_latest_shorts()` 正確回傳今天的 Shorts 清單
- [ ] 已處理影片不會重複下載
- [ ] `download_audio()` 成功產生 mp3 檔
- [ ] 下載失敗時有清楚的錯誤訊息
- [ ] `pytest tests/test_youtube.py tests/test_downloader.py` 全數通過（使用 mock）
