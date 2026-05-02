# yt-dlp flat-playlist 模式回傳 channel ID 而非 video ID

**日期**：2026-05-03  
**類型**：問題排除

---

## 發生了什麼

使用 yt-dlp `flat-playlist` 模式查詢頻道最新影片時，回傳的第一筆結果 ID 為 `UClPqGpUi47AZYCL318E_zgg`，後續嘗試下載該 ID 時出現 "Video unavailable" 錯誤。

錯誤日誌中的異常跡象：
- video ID 以 `UC` 開頭（YouTube channel ID 的固定前綴）
- 影片標題顯示為 `智慧之聲 - Videos (?s)`（帶有 "Videos" 字樣，是播放清單頁面名稱，非實際影片）

## 根本原因

對 `@channel` 格式的頻道 URL（例如 `https://www.youtube.com/@SomeName`）使用 yt-dlp 的 `flat-playlist` 模式時，yt-dlp 在部分情況下會將「Videos 播放清單頁」本身作為第一個條目回傳，而非實際影片。這是 yt-dlp 解析頻道頁面時的已知不穩定行為：頻道首頁（`/@channel`）可能被視為一個容器，其第一個子項目是播放清單而非影片。

YouTube channel ID 固定以 `UC` 開頭，這個特性可作為防禦性過濾的判斷依據。

## 解法（雙重防禦）

**防禦一：強制指向 /videos 子頁面**

```python
videos_url = channel_url.rstrip("/") + "/videos"
```

在頻道 URL 後附加 `/videos`，讓 yt-dlp 查詢影片清單頁而非頻道首頁，從源頭減少拿到播放清單條目的機率。

**防禦二：ID 格式檢查**

```python
video_id = entry.get("id", "")
if video_id.startswith("UC"):
    logger.warning(
        f"yt-dlp 回傳 channel ID 而非 video ID（{video_id}），跳過：{channel_url}"
    )
    return None
```

即使防禦一未能攔截，若 ID 以 `UC` 開頭則直接視為無效並返回 `None`，不進入後續下載流程。

## 風險與注意事項

- `UC` 前綴過濾是基於 YouTube 目前的 ID 命名慣例。若 YouTube 未來改變 channel ID 格式，此防禦規則可能失效（目前幾乎沒有變更先例，低風險）。
- `/videos` 附加方式假設頻道 URL 為標準格式（`/@name` 或 `/channel/UCxxx`）。若 URL 本身已含有子路徑（例如 `/@name/streams`），附加 `/videos` 後會產生錯誤路徑。
- 若 `return None` 被觸發，本次不會寄信，但不會拋出錯誤。需確保呼叫端對 `None` 回傳有明確的跳過處理。

## 參考資料

- YouTube channel ID 格式說明：以 `UC` 開頭，長 24 字元
- yt-dlp `extract_flat` 模式文件：[yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
