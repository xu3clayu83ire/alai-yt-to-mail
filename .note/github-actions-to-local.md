# 從 GitHub Actions 改為本機執行的完整過程

**日期**：2026-05-01  
**類型**：問題排除 + 架構決策

---

## 發生了什麼

原本計畫使用 GitHub Actions 每天定時執行 yt-to-mail，但遭遇一連串問題，最終改為本機執行。

---

## 問題一：YouTube Bot 偵測

**錯誤訊息：**
```
ERROR: [youtube] Sign in to confirm you're not a bot.
Use --cookies-from-browser or --cookies for the authentication.
```

**根本原因：**  
GitHub Actions 使用 Microsoft Azure 資料中心 IP，YouTube 識別為已知爬蟲來源，要求登入驗證。

**嘗試的解法：**
1. 匯出瀏覽器 YouTube cookies → 存入 GitHub Secret `YOUTUBE_COOKIES` → 第一次成功，之後 Google 吊銷該 session
2. 改用 `web_creator` player client → 需要 GVS PO Token，沒有 Token 只剩圖片可下載
3. 改用 `ios`/`android` player client → 這兩個 client 不支援 cookies，被 yt-dlp 跳過
4. 移除 cookies，單獨用 `ios`/`android` → Azure IP 同樣被封鎖

**結論：** Azure 資料中心 IP 被 YouTube 全面封鎖，不管任何 client 或 cookies 組合都無效。

---

## 問題二：OpenAI Whisper API 額度用盡

**錯誤訊息：**
```
Error code: 429 - {'error': {'message': 'You exceeded your current quota...', 'type': 'insufficient_quota'}}
```

**根本原因：**  
OpenAI 帳號沒有剩餘額度，Whisper API 無法呼叫。

**解法：**  
改用本地 `openai-whisper` 套件，在本機執行模型推論，完全免費。

---

## 問題三：本機缺少 ffmpeg

**錯誤訊息：**
```
[WinError 2] 系統找不到指定的檔案
```

**根本原因：**  
`openai-whisper` 套件內部呼叫系統 ffmpeg 解碼音訊，但本機沒有安裝 ffmpeg。

**嘗試的解法：**
1. `winget install Gyan.FFmpeg` → 安裝過程因需同意條款而中斷，實際未安裝成功
2. 設定 `imageio-ffmpeg` PATH → Whisper 在 subprocess 中呼叫 ffmpeg，Windows 不繼承 Python 更新的 PATH
3. 將 m4a 先轉 WAV 再讓 Whisper 讀 WAV → Whisper 讀 WAV 時**仍會**再呼叫一次系統 ffmpeg

**最終解法：**  
用 `imageio_ffmpeg` 內建的 ffmpeg 執行檔將音訊直接解碼為 numpy array，繞過 Whisper 所有內部 ffmpeg 呼叫：

```python
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
result = subprocess.run(
    [ffmpeg_exe, "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "f32le", "-loglevel", "quiet", "-"],
    capture_output=True,
)
audio = np.frombuffer(result.stdout, dtype=np.float32)
model.transcribe(audio, fp16=False)  # 傳 numpy array，不傳檔案路徑
```

---

## 最終架構：本機 + Windows 工作排程器

| 元件 | 原計畫 | 最終 |
|------|--------|------|
| 排程 | GitHub Actions（每天 UTC 00:00） | Windows 工作排程器（每天 08:00） |
| YouTube 下載 | yt-dlp on Azure | yt-dlp on 本機（家用 IP） |
| 語音轉文字 | OpenAI Whisper API | 本地 openai-whisper 模型 |
| 音訊格式 | mp3（需 ffmpeg） | m4a 原始格式 |
| ffmpeg | 系統安裝 | imageio-ffmpeg（pip 套件內建） |
| 費用 | Whisper API 計費 | 完全免費 |

**GitHub repo 保留用途：** 程式碼備份與版本控制，Actions workflow 不再使用。

---

## 風險與注意事項

- **電腦需保持開機**：工作排程器依賴本機，電腦關機當天不會執行
- **YouTube cookies 不再需要**：家用 IP 不被封鎖，但若 YouTube 政策改變仍可能需要
- **Whisper base 模型**：中文辨識準確度良好，若需更高精度可改用 `small` 或 `medium` 模型（但速度較慢）
- **imageio-ffmpeg 版本**：ffmpeg 執行檔隨套件版本更新，若 yt-dlp 更新後格式改變，可能需要升級套件

---

## 參考資料

- [yt-dlp FAQ: cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [openai-whisper GitHub](https://github.com/openai/whisper)
- [imageio-ffmpeg PyPI](https://pypi.org/project/imageio-ffmpeg/)
