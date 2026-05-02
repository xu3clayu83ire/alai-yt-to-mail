# YouTube Shorts 音訊格式不可用

**日期**：2026-05-01  
**類型**：問題排除

---

## 發生了什麼

解決 bot 偵測問題後，yt-dlp 仍然失敗，錯誤訊息改為：

```
ERROR: [youtube] 4EL03MQgOg4: Requested format is not available.
Use --list-formats for a list of available formats
```

## 根本原因

原本的格式設定為：

```python
"format": "bestaudio/best"
```

YouTube Shorts 的可用格式與一般影片不同，部分 Shorts 沒有符合 `bestaudio` 條件的獨立音訊串流，導致格式比對失敗。

## 解法（第一次嘗試，無效）

改為依序嘗試多種音訊格式：

```python
"format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
```

仍然失敗。原因：YouTube Shorts **根本沒有獨立的音訊串流**，`bestaudio` 系列格式全部找不到。

## 解法（最終有效）

改為下載合併格式（影片＋音訊），再交給 ffmpeg 擷取音訊：

```python
"format": "best[ext=mp4]/best"
```

ffmpeg 的 `FFmpegExtractAudio` 後製程序會從 mp4 中擷取音訊並轉為 mp3，最終結果相同。

## 風險與注意事項

- Shorts 只有合併格式（影片+音訊），沒有獨立音訊串流，這是 YouTube 的設計，不是 bug
- 下載合併格式會比純音訊多佔一些頻寬，但 Shorts 通常很短，影響不大
- 可用 `yt-dlp --list-formats <video_url>` 列出特定影片的所有可用格式，用來診斷類似問題
