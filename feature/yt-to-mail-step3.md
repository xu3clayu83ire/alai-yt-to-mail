# yt-to-mail — Step 3：語音轉文字（OpenAI Whisper API）

**負責 Agent**：cdk-coder  
**驗證 Agent**：cdk-tester  
**依賴**：Step 2 完成

---

## 目標

將 Step 2 下載的 mp3 音訊檔透過 OpenAI Whisper API 轉換為文字稿。

---

## 技術規格

### transcriber.py

#### 函式：`transcribe(audio_path: str) -> TranscriptResult`

```python
@dataclass
class TranscriptResult:
    text: str              # 完整文字稿
    language: str          # 偵測到的語言（'zh'、'en' 等）
    duration_seconds: float
```

#### 實作細節
- 使用 `openai.Audio.transcriptions.create` API
- Model：`whisper-1`
- Response format：`verbose_json`（含語言偵測與時間戳）
- 檔案大小限制：25MB（Whisper API 限制）
  - 若超過，自動切割後分段轉錄再合併

#### 錯誤處理
- API 呼叫失敗：最多重試 3 次（指數退避：2s, 4s, 8s）
- 超過大小限制：記錄警告並切割處理
- 拋出 `TranscriptionError`（含原始錯誤訊息）

---

## 驗收條件

- [ ] 成功轉錄測試音訊檔（30 秒內）
- [ ] 正確偵測語言
- [ ] API 失敗時正確重試
- [ ] `pytest tests/test_transcriber.py` 通過（mock Whisper API）
