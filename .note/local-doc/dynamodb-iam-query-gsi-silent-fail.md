# DynamoDB GSI Query 權限缺失導致重複寄信，加上 URL section path 丟失導致取錯影片類型

**日期**：2026-05-03  
**類型**：問題排除

---

## 發生了什麼

受影響用戶：amberprosty@gmail.com  
症狀：同一頻道 `@melrobbins/shorts` 訂閱三次（send_time 分別 09:20 / 09:25 / 09:30），每次排程執行都收到一樣的影片音訊，且影片是一般影片而非 Shorts。

問題拆解後確認為兩個獨立 bug 同時發作：

1. IAM 缺少 `dynamodb:Query` 對 GSI 的授權，導致 history 查詢靜默失敗，每次都誤判「從未寄過」而重複寄出
2. URL 解析時丟棄 `/shorts` section path，導致 scheduler 抓到的是一般影片而非 Shorts

---

## Bug 1：IAM 缺少 dynamodb:Query GSI 權限

### 根本原因

`yt-to-mail-scheduler` IAM User 的 `WriteReadHistory` PolicyStatement 只有：

```typescript
actions: ['dynamodb:PutItem', 'dynamodb:Scan'],
resources: [`arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-history`]
```

缺少：
1. `dynamodb:Query` action
2. GSI resource ARN：`table/yt-to-mail-history/index/*`

DynamoDB IAM 的關鍵行為：**GSI 的 Query 授權必須獨立列出 `table/name/index/*` 資源，不包含在 `table/name` 資源之內**。即使 table ARN 已列出，對 GSI 執行 Query 仍會被拒絕。

### 錯誤訊息（原文）

scheduler log 中每次呼叫 `get_sent_video_ids()` 都出現：

```
AccessDeniedException: User: arn:aws:iam::029939913757:user/yt-to-mail-scheduler 
is not authorized to perform: dynamodb:Query on resource: 
arn:aws:dynamodb:us-east-1:029939913757:table/yt-to-mail-history/index/user_id-index
```

### 為何難以發現

- `PutItem`（寫入 history）成功，DynamoDB Console 看得到記錄 → 誤以為 history 功能正常
- `Query`（讀取 history）被 `except` 區塊捕捉後回傳空 set，外部無任何 alarm 或 metric
- 症狀（重複寄信）和根因（IAM 缺權限）之間有兩層間接關係：IAM 拒絕 → except 吞掉 → 回傳空 set → 誤判從未寄過 → 重複寄出

### 修正方式

`lib/yt-to-mail-backend-stack.ts` 的 `WriteReadHistory` PolicyStatement：

```typescript
new iam.PolicyStatement({
  sid: 'WriteReadHistory',
  actions: [
    'dynamodb:PutItem',
    'dynamodb:Scan',
    'dynamodb:Query',   // 查詢已寄送影片清單（透過 user_id-index GSI）
  ],
  resources: [
    `arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-history`,
    `arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-history/index/*`,  // GSI 必須單獨列出
  ],
})
```

---

## Bug 2：URL 解析丟失 /shorts section path

### 根本原因

問題發生在兩個地方的邏輯不一致：

**lambda/api/routers/public.py** 的 regex 只擷取 handle，將 section path 丟棄：

```python
# 舊版（有問題）
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)(?:/.*)?$")
# @melrobbins/shorts → stored as @melrobbins（/shorts 被丟棄）
```

**scheduler/processor.py** 的 `_get_recent_videos()` 無條件附加 `/videos`：

```python
# 舊版（有問題）
url = f"{channel_url.rstrip('/')}/videos"
# 即使能正確儲存 @melrobbins/shorts，也會變成 @melrobbins/shorts/videos（無效路徑）
```

### 修正方式

**public.py**：更新 regex 明確擷取並保留 section path

```python
_HANDLE_PATTERN = re.compile(r"^/@([^/]+?)((?:/(?:videos|shorts|streams|live|playlists|community))?)$")
# group(1) = handle, group(2) = section（"/shorts" 或空字串）
```

**processor.py**：新增 `_build_channel_content_url()` 判斷是否已有 section path

```python
_YOUTUBE_SECTION_SUFFIXES = ("/videos", "/shorts", "/streams", "/live", "/playlists", "/community")

def _build_channel_content_url(channel_url: str) -> str:
    cleaned = channel_url.rstrip("/")
    for suffix in _YOUTUBE_SECTION_SUFFIXES:
        if cleaned.endswith(suffix):
            return cleaned
    return cleaned + "/videos"
```

---

## 風險與注意事項

1. **既有訂閱資料已儲存為錯誤格式**：bug 修正前訂閱的 `@channel/shorts` 頻道，其 `channel_url` 欄位可能已儲存為 `@channel`（section path 遺失）。修正程式碼後，這些舊資料不會自動修正，需要確認是否需要 migration。

2. **`get_sent_video_ids()` 的 except fallback 仍是隱患**：目前修正了 IAM 權限，但 except 吞掉錯誤的邏輯仍在。若未來再次發生任何 DynamoDB 存取錯誤，仍會靜默失敗並重複寄信。應新增 CloudWatch Metric 或 alarm 讓 fallback 行為可被監測。

3. **GSI ARN 需在每次新增 GSI 時主動更新 IAM**：這次遺漏 `user_id-index` 的授權，下次若新增其他 GSI（例如未來的 `channel_id-index`）必須記得同步更新 PolicyStatement。

---

## 防範建議（規格層面）

1. **IAM 設計規格必須明列所有資料存取路徑**：每個 DynamoDB 操作（GetItem / Query / Scan）都必須對應列出涉及的 table ARN 與所有 GSI ARN

2. **例外處理不得靜默吞掉業務關鍵錯誤**：`get_sent_video_ids()` 的 except 應額外觸發 CloudWatch Metric 或 alarm，讓 fallback 行為（回傳空 set）可被監測

3. **URL 正規化規格必須明確說明 section path 保留行為**：訂閱時的 URL 解析、儲存格式，以及 scheduler 使用時的 URL 建構邏輯，三者必須在規格中對齊

---

## 參考資料

- [AWS DynamoDB IAM 文件：Specifying Conditions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/specifying-conditions.html)
- [AWS IAM 文件：Actions defined by Amazon DynamoDB](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazondynamodb.html)
- DynamoDB GSI resource ARN 格式：`arn:aws:dynamodb:<region>:<account>:table/<table-name>/index/<index-name>`
