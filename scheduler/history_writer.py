"""
history_writer.py — DynamoDB history 寫入模組

負責將每次排程任務的執行結果寫入 yt-to-mail-history 資料表。
記錄包含成功（done）、失敗（failed）、跳過（skipped_language）三種狀態，
失敗時額外記錄 error_message（截斷至 500 字元），方便事後排查問題。
每筆記錄使用 uuid4 作為主鍵，確保在並行（未來擴展）場景下不會衝突。
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

import config

logger = logging.getLogger(__name__)

# 有效的 history status 值
VALID_STATUSES = {"done", "failed", "skipped_language"}

# error_message 最大長度（DynamoDB String 型別無硬限制，但為節省費用與可讀性截斷）
ERROR_MESSAGE_MAX_LENGTH = 500

# boto3 DynamoDB 資源快取：模組載入時建立一次，避免每次呼叫都重新建立 session
_dynamodb = boto3.resource("dynamodb", region_name=config.get_aws_region())

# 執行期記憶體快取：補償 DynamoDB GSI 最終一致性延遲。
# 同一 scheduler 執行週期內，新寄出的 video_id 立即記入此 dict，
# 確保同一輪的後續訂閱能即時看到，不依賴 GSI 更新時機。
# key 格式："{user_id}|{channel_url}"，value：已成功寄送的 video_id set。
_runtime_sent_cache: dict[str, set[str]] = {}


def _cache_key(user_id: str, channel_url: str) -> str:
    return f"{user_id}|{channel_url}"


def get_sent_video_ids(user_id: str, channel_url: str) -> set[str]:
    """
    查詢此 user_id + channel_url 所有 status=done 的 video_id，回傳 set。
    以 user_id-index GSI 查詢，再以 channel_url 過濾，
    確保同一用戶對同一頻道不論有幾個訂閱都不重複寄送相同影片。
    同時合併 _runtime_sent_cache，補償 DynamoDB GSI 最終一致性延遲：
    同一輪 scheduler 執行內，第 1 個訂閱寄完後立即可被後續訂閱的查詢看到。
    舊記錄若無 channel_url 欄位則不參與去重（不影響正確性，只是不阻擋舊資料）。
    若查詢失敗，保守回傳空 set（允許繼續處理），並記錄警告。
    """
    history_table_name = config.get_history_table()
    runtime_ids = _runtime_sent_cache.get(_cache_key(user_id, channel_url), set())
    try:
        table = _dynamodb.Table(history_table_name)
        response = table.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(user_id),
            FilterExpression=(
                Attr("channel_url").eq(channel_url)
                & Attr("status").eq("done")
            ),
            ProjectionExpression="video_id",
        )
        dynamo_ids = {item["video_id"] for item in response.get("Items", [])}
        return dynamo_ids | runtime_ids
    except Exception as e:
        logger.warning(
            f"查詢已寄送影片清單時發生錯誤，回傳 runtime cache 允許繼續處理 - "
            f"user_id={user_id}, channel_url={channel_url}, error={e}"
        )
        return set(runtime_ids)


def write_history(
    user_id: str,
    subscription_id: str,
    channel_url: str,
    video_id: str,
    video_title: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """
    將一次排程任務的執行結果寫入 history 資料表。
    使用 uuid4 產生唯一 id，sent_at 記錄寫入時的 UTC 時間（ISO 8601 格式），
    確保即使在相同分鐘內有多筆紀錄，時間戳記仍能精確區分。
    若 DynamoDB PutItem 失敗，僅記錄本機 log 而不拋出例外，
    避免 history 寫入失敗影響排程器的整體運行。
    """
    if status not in VALID_STATUSES:
        logger.warning(f"無效的 status 值：{status}，使用 'failed' 取代")
        status = "failed"

    history_table_name = config.get_history_table()

    # 建立 history 記錄項目
    item: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "subscription_id": subscription_id,
        "channel_url": channel_url,
        "video_id": video_id,
        "video_title": video_title,
        "sent_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
    }

    # 失敗時額外記錄 error_message（截斷至 500 字元以控制 DynamoDB item 大小）
    if error_message is not None:
        truncated = error_message[:ERROR_MESSAGE_MAX_LENGTH]
        if len(error_message) > ERROR_MESSAGE_MAX_LENGTH:
            truncated += "...[截斷]"
        item["error_message"] = truncated

    try:
        table = _dynamodb.Table(history_table_name)
        table.put_item(Item=item)
        logger.info(
            f"history 寫入成功 - subscription_id={subscription_id}, "
            f"video_id={video_id}, status={status}"
        )
        # 寫入成功後立即更新 runtime cache，補償 GSI 最終一致性延遲
        if status == "done" and video_id:
            key = _cache_key(user_id, channel_url)
            _runtime_sent_cache.setdefault(key, set()).add(video_id)
    except Exception as e:
        # DynamoDB 寫入失敗僅記錄 log，不中斷流程
        logger.error(
            f"history 寫入失敗（僅記錄 log，不重試）- "
            f"subscription_id={subscription_id}, error={e}",
            exc_info=True,
        )
