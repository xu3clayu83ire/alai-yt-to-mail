# yt-to-mail-step15：v3 排程器自動取消計數器

## 前提條件與相依 Step

- **先決條件**：step9 基礎設施已存在（subscriptions 表、history 表、scheduler/ 目錄）
- **相依關係**：完全獨立，可與 step10–step14 所有 step 完全平行執行
- **後續相依**：無

---

## 功能名稱

排程器自動取消訂閱計數器：`processor.py` 計數邏輯 + `gmail_sender.py` 取消通知信

---

## 目標

當頻道連續 N 天沒有新影片（`status=skipped_duplicate`）時，自動取消訂閱並寄送通知信：
1. `processor.py`：在 `status=done` 時重置計數器，在 `status=skipped_duplicate` 時累加計數器並判斷是否觸發自動取消
2. `gmail_sender.py`：新增 `send_auto_cancel_email` 函式，發送自動取消通知（含重新訂閱連結）
3. 計數器操作透過新增的 `dynamo_updater.py` 模組集中管理（單一職責原則）

---

## 技術規格

### 影響檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `scheduler/processor.py` | **修改** | 加入計數器邏輯（重置 / 累加 / 觸發取消） |
| `scheduler/gmail_sender.py` | **修改** | 新增 `send_auto_cancel_email` 函式 |
| `scheduler/dynamo_updater.py` | **新增** | DynamoDB 訂閱欄位更新函式（計數器、刪除） |

---

### 資料模型更新（DynamoDB Schema-less）

`yt-to-mail-subscriptions` 表新增欄位（無需修改 Key Schema）：

| 欄位名稱 | 型別 | 預設值 | 說明 |
|---------|------|-------|------|
| `auto_cancel_days` | Number (Decimal) | 3 | 連續無新影片幾天後自動取消 |
| `no_new_video_days` | Number (Decimal) | 0 | 當前連續無新影片天數（計數器） |

> 舊有訂閱（無此欄位）在排程器讀取時以 `int(item.get("auto_cancel_days", 3))` 取得預設值，不需要 backfill。

---

### dynamo_updater.py（新增）

```python
"""
dynamo_updater.py — DynamoDB 訂閱欄位更新模組

集中管理排程器對 subscriptions 表的寫入操作：
- 重置 no_new_video_days 計數器（status=done 時）
- 累加 no_new_video_days 計數器（status=skipped_duplicate 時）
- 刪除訂閱（自動取消時）
"""

import logging
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

import config

logger = logging.getLogger(__name__)

_dynamodb = boto3.resource("dynamodb", region_name=config.get_aws_region())


def reset_no_new_video_days(subscription_id: str) -> None:
    """
    將訂閱的 no_new_video_days 重置為 0。
    當本次處理 status=done 時呼叫，表示頻道有新影片，計數器清零。
    若更新失敗，僅記錄 warning，不中斷主流程。
    """
    ...


def increment_no_new_video_days(subscription_id: str) -> int:
    """
    將訂閱的 no_new_video_days 加 1，回傳更新後的值。
    使用 DynamoDB ADD 操作（原子性遞增），避免並行問題。
    若欄位不存在（舊資料），ADD 操作會自動從 0 開始計算。
    若更新失敗，記錄 warning 並回傳 -1（讓呼叫端跳過自動取消判斷）。
    """
    ...


def delete_subscription(subscription_id: str) -> None:
    """
    刪除指定訂閱（自動取消觸發時呼叫）。
    若刪除失敗，記錄 error 並拋出例外，由呼叫端決定是否繼續。
    """
    ...
```

**`increment_no_new_video_days` 實作要點**：

```python
# DynamoDB UpdateItem with ADD expression（原子遞增）
response = table.update_item(
    Key={"id": subscription_id},
    UpdateExpression="ADD no_new_video_days :inc",
    ExpressionAttributeValues={":inc": Decimal("1")},
    ReturnValues="UPDATED_NEW",
)
# 取得更新後的值
updated_value = int(response["Attributes"].get("no_new_video_days", 0))
return updated_value
```

---

### processor.py 修改規格

#### 修改位置：`process_subscription` 函式

在現有流程的兩個關鍵點插入計數器邏輯：

**關鍵點 A（status=done，寄信成功後）**：

```python
# Step 7：寫入 history（成功）
history_writer.write_history(...)

# [新增] Step 7.5：重置無新影片計數器
dynamo_updater.reset_no_new_video_days(subscription_id)

logger.info(f"[sub:{subscription_id}] 處理完成 - video_id={video_id}, status=done")
return {..., "status": "done"}
```

**關鍵點 B（status=skipped_duplicate，所有影片已寄過）**：

```python
# 原有邏輯：寄「無新影片通知」信
# [移除] gmail_sender.send_no_new_video_email(...)  # 不再寄「無新影片」通知信
# [保留] 仍回傳 skipped_duplicate，但改為計數器累加邏輯

# [新增] 累加計數器
current_days = dynamo_updater.increment_no_new_video_days(subscription_id)

if current_days >= 0 and current_days >= int(subscription.get("auto_cancel_days", 3)):
    # 觸發自動取消
    logger.info(
        f"[sub:{subscription_id}] 連續 {current_days} 天無新影片，"
        f"達到上限 {subscription.get('auto_cancel_days', 3)} 天，自動取消訂閱"
    )
    # 寄取消通知信
    gmail_sender.send_auto_cancel_email(
        recipient_email=recipient_email,
        channel_name=channel_name,
        auto_cancel_days=int(subscription.get("auto_cancel_days", 3)),
        channel_url=channel_url,
    )
    # 刪除訂閱
    dynamo_updater.delete_subscription(subscription_id)

    return {
        "video_id": None,
        "video_title": None,
        "status": "auto_cancelled",
        "error_message": None,
    }

return {
    "video_id": None,
    "video_title": None,
    "status": "skipped_duplicate",
    "error_message": None,
}
```

#### process_subscription 函式簽章不變

- 輸入：`subscription: dict[str, Any]`（新增讀取 `auto_cancel_days`、`no_new_video_days`）
- 輸出：結果 dict，新增 `status="auto_cancelled"` 可能值

#### 從 subscription dict 讀取新欄位

```python
auto_cancel_days: int = int(subscription.get("auto_cancel_days", 3))
```

> 排程器讀取欄位時，DynamoDB 回傳 Decimal，使用 `int()` 轉換。

---

### gmail_sender.py 修改規格

#### 新增 `send_auto_cancel_email` 函式

```python
def send_auto_cancel_email(
    recipient_email: str,
    channel_name: str,
    auto_cancel_days: int,
    channel_url: str,
) -> None:
    """
    當訂閱因連續 N 天無新影片而自動取消時，寄送通知信給訂閱者。
    信中說明取消原因，並提供重新訂閱連結，讓用戶可輕鬆重新訂閱。
    重新訂閱連結指向公開訂閱頁（從 config 讀取 FRONTEND_URL，預設空字串）。
    """
    sender = config.get_gmail_sender()
    subject = f"[yt-to-mail] 您對「{channel_name}」的訂閱已自動取消"

    # 公開訂閱頁連結（供用戶重新訂閱）
    frontend_url = config.get_frontend_url()  # 新增 config 函式
    resubscribe_url = frontend_url if frontend_url else "（請至訂閱頁重新訂閱）"

    plain_body = (
        f"您好，\n\n"
        f"由於頻道「{channel_name}」已連續 {auto_cancel_days} 天未發布新影片，\n"
        f"系統已自動取消您對此頻道的訂閱。\n\n"
        f"若您仍希望追蹤此頻道，可透過以下連結重新訂閱：\n"
        f"{resubscribe_url}\n\n"
        f"感謝您使用 yt-to-mail！"
    )

    html_body = f"""
<html>
  <body>
    <p>您好，</p>
    <p>由於頻道「<strong>{channel_name}</strong>」已連續 <strong>{auto_cancel_days} 天</strong>未發布新影片，</p>
    <p>系統已自動取消您對此頻道的訂閱。</p>
    <hr>
    <p>若您仍希望追蹤此頻道，可透過以下連結重新訂閱：</p>
    <p><a href="{resubscribe_url}">{resubscribe_url}</a></p>
    <p>感謝您使用 yt-to-mail！</p>
  </body>
</html>
"""

    message = MIMEMultipart("alternative")
    message["to"] = recipient_email
    message["from"] = sender
    message["subject"] = subject
    message.attach(MIMEText(plain_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    service = _get_gmail_service()
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

    logger.info(f"自動取消通知已寄出至 {recipient_email}，頻道：{channel_name}，天數：{auto_cancel_days}")
```

---

### config.py 更新

新增 `get_frontend_url` 函式（讀取 `.env` 中的 `FRONTEND_URL`）：

```python
def get_frontend_url() -> str:
    """
    取得前端公開訂閱頁 URL，用於自動取消通知信中的重新訂閱連結。
    若未設定則回傳空字串，通知信中顯示提示文字。
    """
    return os.environ.get("FRONTEND_URL", "")
```

**.env.example 新增**：

```
FRONTEND_URL=https://xxxxx.cloudfront.net
```

---

### IAM 權限更新

排程器 IAM Policy（`yt-to-mail-scheduler-policy`）需新增 `dynamodb:UpdateItem` 與 `dynamodb:DeleteItem` 權限：

```typescript
// lib/yt-to-mail-backend-stack.ts 中 schedulerPolicy 的 ReadSubscriptions 語句更新
new iam.PolicyStatement({
  sid: 'ReadWriteSubscriptions',
  effect: iam.Effect.ALLOW,
  actions: [
    'dynamodb:Query',
    'dynamodb:GetItem',
    'dynamodb:Scan',
    'dynamodb:UpdateItem',   // 新增：計數器累加 / 重置
    'dynamodb:DeleteItem',   // 新增：自動取消刪除訂閱
  ],
  resources: [
    `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-subscriptions`,
    `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-subscriptions/index/*`,
  ],
}),
```

> **注意**：此 CDK Stack 修改屬於本 step 的一部分，由本 step 的 Coder 負責。

---

### 環境變數

| 變數名稱 | 說明 | 來源 |
|---------|------|------|
| `FRONTEND_URL` | 前端公開訂閱頁 URL，用於通知信連結 | `.env` |

---

## 驗收標準

- [ ] `status=done` 時呼叫 `reset_no_new_video_days`，DynamoDB 中 `no_new_video_days` 更新為 0
- [ ] `status=skipped_duplicate` 時呼叫 `increment_no_new_video_days`，計數器加 1
- [ ] 計數器達到 `auto_cancel_days` 時：呼叫 `send_auto_cancel_email`，刪除訂閱，status 回傳 `auto_cancelled`
- [ ] 計數器未達上限時：回傳 `skipped_duplicate`，不刪除訂閱
- [ ] `send_auto_cancel_email` 信件含頻道名稱、天數、重新訂閱連結
- [ ] 舊有訂閱（無 `auto_cancel_days` 欄位）以預設值 3 運作，不崩潰
- [ ] `dynamo_updater.increment_no_new_video_days` 使用原子 ADD 操作（非 read-then-write）
- [ ] CDK IAM Policy 更新（`UpdateItem`、`DeleteItem` 加入 subscriptions 資源）
- [ ] `cdk synth` + `tsc --noEmit` 通過（CDK 修改部分）

---

## 工作分派

### 本 Step 指派
- **Coder B**（排程器軌道）：完全獨立，可最先執行（與 step10–step14 完全平行）

### 平行協作
- **Coder A** 同時執行 step10 → step11（後端軌道）
- step15 完成後，Coder B 繼續接手 step12 → step13（前端軌道）

---

## 注意事項與限制

- `send_no_new_video_email`（原有函式）：依照需求，`skipped_duplicate` 時改為累加計數器，**不再**每次都寄「無新影片通知」信，避免用戶頻繁收到無意義通知
- DynamoDB ADD 操作（原子遞增）確保即使多個排程同時執行（未來擴展）也不會有競態問題
- `status="auto_cancelled"` 是新增的回傳值，`run.py` 的日誌記錄需能正確處理此狀態（不需要特別修改，因 run.py 只記錄 status string）
- `dynamo_updater.delete_subscription` 失敗時拋出例外，由 `process_subscription` 的外層 except 捕捉並記錄 `status=failed`
- 所有函式必須包含繁體中文函式級註解
- 禁止使用 `any` 型別，所有 Python type hints 正確標注
