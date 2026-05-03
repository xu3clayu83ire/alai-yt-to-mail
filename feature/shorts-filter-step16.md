# Shorts 篩選功能 — step16

## 功能名稱

Shorts 篩選功能：訂閱 URL 含 `/shorts` 時，排程器只處理 Shorts 影片

---

## 目標

當用戶以 `https://www.youtube.com/@handle/shorts` 訂閱頻道時，
目前系統會丟棄 `/shorts` 路徑，導致排程器抓取一般影片而非 Shorts。
本功能修正 URL 解析邏輯，保留 shorts 標記並傳遞至排程器，
使排程器依 `channel_url` 是否以 `/shorts` 結尾，決定查詢目標播放清單。

---

## 技術規格

### AWS 服務與資源

無新增或修改的 AWS 資源，不涉及 CDK、IAM 或 DynamoDB Schema 變更。

---

### CDK Stack 結構

無變更。

---

### 影響檔案清單

| 檔案 | 類型 | 變更說明 |
|------|------|---------|
| `lambda/api/routers/channels.py` | Lambda API | URL 解析邏輯：保留 `/shorts` 標記於正規化輸出 |
| `lambda/api/routers/public.py` | Lambda API | `_parse_channel_url` 函式：保留 `/shorts` 標記於正規化輸出 |
| `scheduler/processor.py` | 本機排程 | `_get_recent_videos`：依 `channel_url` 決定播放清單 URL |

---

### URL 解析邏輯變更

#### 正規化輸出格式規則

| 輸入 URL 路徑 | 正規化輸出 `channel_url` |
|-------------|------------------------|
| `/@handle` | `https://www.youtube.com/@handle` |
| `/@handle/videos` | `https://www.youtube.com/@handle` |
| `/@handle/shorts` | `https://www.youtube.com/@handle/shorts` |
| `/@handle/shorts/` | `https://www.youtube.com/@handle/shorts` |
| `/@handle/shorts/UCxxx` | `https://www.youtube.com/@handle/shorts` |
| `/channel/UCxxx` | `https://www.youtube.com/channel/UCxxx`（不變）|
| `/channel/UCxxx/shorts` | `https://www.youtube.com/channel/UCxxx`（不支援，行為不變）|

**規則摘要**：
- `/@handle` 後的子路徑若為 `/shorts`（含任何後續子路徑），正規化結果追加 `/shorts`
- `/@handle` 後的子路徑為其他任何值（`/videos`、`/streams` 等），正規化結果不含後綴
- `/channel/UCxxx` 格式：一律不附加 `/shorts`（YouTube 對 channel ID URL 無 /shorts 分頁）

#### `channels.py` — 修改前後對照

**修改前**：
```python
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(?:/.*)?$")

# 在 verify_channel 中：
handle_match = _HANDLE_PATTERN.match(path)
if handle_match:
    handle = handle_match.group(1)
    normalized_url = f"https://www.youtube.com/@{handle}"
```

**修改後**：
```python
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(?:/(shorts)(?:/.*)?|(?:/[^/]+)?(?:/.*)?)?$")

# 在 verify_channel 中：
handle_match = _HANDLE_PATTERN.match(path)
if handle_match:
    handle = handle_match.group(1)
    is_shorts = handle_match.group(2) == "shorts"
    suffix = "/shorts" if is_shorts else ""
    normalized_url = f"https://www.youtube.com/@{handle}{suffix}"
```

實際正規表達式可使用更易讀的具名群組，或拆分為兩步驟判斷（先取 handle，再判斷子路徑是否以 `/shorts` 開頭）：

```python
# 推薦寫法：取 handle 後，獨立判斷子路徑
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(/.*)?$")

handle_match = _HANDLE_PATTERN.match(path)
if handle_match:
    handle = handle_match.group(1)
    subpath = handle_match.group(2) or ""           # 可能為 "" / "/videos" / "/shorts" / "/shorts/xxx"
    is_shorts = subpath == "/shorts" or subpath.startswith("/shorts/")
    suffix = "/shorts" if is_shorts else ""
    normalized_url = f"https://www.youtube.com/@{handle}{suffix}"
```

`channel_id` 與 `channel_name` 在原型階段仍暫以 `handle` 填充，不受本次變更影響。

#### `public.py` — `_parse_channel_url` 修改前後對照

**修改前**：
```python
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(?:/.*)?$")

handle_match = _HANDLE_PATTERN.match(path)
if handle_match:
    handle = handle_match.group(1)
    normalized_url = f"https://www.youtube.com/@{handle}"
    return normalized_url, handle, handle
```

**修改後**（與 `channels.py` 邏輯完全一致）：
```python
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(/.*)?$")

handle_match = _HANDLE_PATTERN.match(path)
if handle_match:
    handle = handle_match.group(1)
    subpath = handle_match.group(2) or ""
    is_shorts = subpath == "/shorts" or subpath.startswith("/shorts/")
    suffix = "/shorts" if is_shorts else ""
    normalized_url = f"https://www.youtube.com/@{handle}{suffix}"
    return normalized_url, handle, handle
```

---

### 排程器 `_get_recent_videos` 邏輯變更

#### 修改前後對照

**修改前**（`processor.py` 第 63 行）：
```python
def _get_recent_videos(channel_url: str) -> list[dict[str, Any]]:
    videos_url = channel_url.rstrip("/") + "/videos"
```

**修改後**：
```python
def _get_recent_videos(channel_url: str) -> list[dict[str, Any]]:
    # 若 channel_url 以 /shorts 結尾，直接使用該 URL
    # （yt-dlp 可直接解析 /@handle/shorts 播放清單，不需 append /videos）
    # 否則 append /videos 取一般影片清單（維持現有行為）
    base = channel_url.rstrip("/")
    if base.endswith("/shorts"):
        videos_url = base
    else:
        videos_url = base + "/videos"
```

**其餘邏輯不變**：`playlist_items`、`extract_flat`、UC 過濾、錯誤處理均保持現有實作。

---

### 向下相容說明

- 舊有訂閱的 `channel_url` 格式為 `https://www.youtube.com/@handle`（不含 `/shorts`），
  `base.endswith("/shorts")` 判斷為 False，走 `+ "/videos"` 分支，行為完全不變。
- 不需要對 DynamoDB 現有資料進行 backfill。
- `/channel/UCxxx` 格式不含 `/shorts`，行為不變。

---

### API 介面

無新增端點。`POST /channels/verify` 回應的 `channel_url` 欄位格式依輸入 URL 含 `/shorts` 與否而不同：

- 輸入 `https://www.youtube.com/@melrobbins/shorts`
  → 回應 `channel_url: "https://www.youtube.com/@melrobbins/shorts"`
- 輸入 `https://www.youtube.com/@melrobbins`
  → 回應 `channel_url: "https://www.youtube.com/@melrobbins"`

---

### 資料模型

無 Schema 變更。`channel_url` 欄位在 DynamoDB 中直接存新格式（含 `/shorts`），
原有欄位定義不需修改（schema-less 自動相容）。

---

### IAM 權限

無變更。

---

### 環境變數

無新增或修改的環境變數。

---

## 驗收條件

- [ ] 輸入 `https://www.youtube.com/@melrobbins/shorts`，`POST /channels/verify` 回應的 `channel_url` 為 `https://www.youtube.com/@melrobbins/shorts`
- [ ] 輸入 `https://www.youtube.com/@melrobbins/shorts/`（尾部斜線），正規化輸出同上（無雙斜線）
- [ ] 輸入 `https://www.youtube.com/@melrobbins`，`POST /channels/verify` 回應的 `channel_url` 為 `https://www.youtube.com/@melrobbins`（不含 `/shorts`）
- [ ] 輸入 `https://www.youtube.com/@melrobbins/videos`，正規化輸出為 `https://www.youtube.com/@melrobbins`（不含任何後綴）
- [ ] `POST /public/subscribe` 傳入 `channel_url: "https://www.youtube.com/@melrobbins/shorts"`，DynamoDB 中存入的 `channel_url` 為 `https://www.youtube.com/@melrobbins/shorts`
- [ ] `POST /public/subscribe` 傳入 `channel_url: "https://www.youtube.com/@melrobbins"`，DynamoDB 中存入的 `channel_url` 為 `https://www.youtube.com/@melrobbins`（不含 `/shorts`）
- [ ] 排程器處理 `channel_url = "https://www.youtube.com/@melrobbins/shorts"` 時，yt-dlp 查詢 URL 為 `https://www.youtube.com/@melrobbins/shorts`（不 append `/videos`）
- [ ] 排程器處理 `channel_url = "https://www.youtube.com/@melrobbins"` 時，yt-dlp 查詢 URL 為 `https://www.youtube.com/@melrobbins/videos`（維持現有行為）
- [ ] 排程器處理舊有 `/channel/UCxxx` 格式訂閱，查詢 URL 為 `/channel/UCxxx/videos`（行為不變）
- [ ] 前端 `defaultValues.channel_url = "https://www.youtube.com/@melrobbins/shorts"` 通過 `POST /channels/verify` 後，回傳 `channel_url` 保留 `/shorts`，供後續 `POST /public/subscribe` 使用
- [ ] Python 函式具備繁體中文函式級註解
- [ ] `tsc --noEmit` 仍通過（無 CDK TypeScript 變更，驗證既有 Stack 未受影響）

---

## 工作分派（單一 Coder）

本功能所有變更集中於 Python 端（Lambda API 與排程器），無 CDK TypeScript 變更，
指派單一 `cdk-coder` 依序實作三個檔案。

### 任務清單

| 順序 | 負責檔案 | 任務描述 |
|------|---------|---------|
| 1 | `lambda/api/routers/channels.py` | 修改 `_HANDLE_PATTERN` 與 `verify_channel` 函式，保留 `/shorts` 標記於 `normalized_url` |
| 2 | `lambda/api/routers/public.py` | 修改 `_parse_channel_url` 函式，與 `channels.py` 邏輯保持一致 |
| 3 | `scheduler/processor.py` | 修改 `_get_recent_videos` 函式，依 `channel_url` 是否以 `/shorts` 結尾決定播放清單 URL |

### 依賴順序

任務 1、2 可平行進行（互相獨立）；任務 3 完全獨立於任務 1、2，可同時開始。

**完全平行，三個檔案可同時開始。**

---

## 開發階段拆分

- Step 16（本 step）：修改 `channels.py`、`public.py`、`processor.py`，完成所有 Shorts 篩選邏輯

---

## 注意事項與限制

1. `_HANDLE_PATTERN` 正規表達式需確保 handle 捕捉群組（group 1）只含 handle 本身，不含 `/shorts` 後綴
2. `rstrip("/")` 必須在 `endswith("/shorts")` 判斷前執行，避免尾部斜線造成判斷失效
3. `/channel/UCxxx/shorts` 在 YouTube 實際上並不存在有效的 Shorts 播放清單頁，故維持不支援的現況
4. `channel_id` 與 `channel_name` 欄位在原型階段仍以 `handle` 填充（非本次修改範疇）
5. 本次變更不涉及任何 CDK TypeScript 或 IAM 修改，`cdk synth` 結果不應改變
