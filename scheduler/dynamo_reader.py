"""
dynamo_reader.py — DynamoDB 訂閱查詢模組

負責查詢當前分鐘到期的訂閱清單。
使用 UTC 時間比對 send_time 欄位，確保不論本機時區為何，
都能正確找到應在此分鐘觸發的訂閱。
"""

import logging
from datetime import datetime, timezone
from typing import Any

import boto3

import config

logger = logging.getLogger(__name__)

# boto3 DynamoDB 資源快取：模組載入時建立一次，避免每次呼叫都重新建立 session
_dynamodb = boto3.resource("dynamodb", region_name=config.get_aws_region())


def get_current_utc_hhmm() -> str:
    """
    取得當前 UTC 時間的 HH:MM 格式字串。
    使用 timezone.utc 確保與系統時區無關，統一使用 UTC 時間，
    避免 Windows 本機時區設定影響排程觸發時間。
    回傳格式範例：'14:30'
    """
    now_utc = datetime.now(timezone.utc)
    return now_utc.strftime("%H:%M")


def get_due_subscriptions() -> list[dict[str, Any]]:
    """
    查詢當前分鐘到期的有效訂閱清單。
    對 subscriptions 表執行 Scan 並篩選 is_active=True 且 send_time 等於當前 UTC HH:MM 的訂閱。
    原型階段訂閱數量少（每用戶上限 5 個），Scan 的額外成本可接受；
    未來若用戶數增加，可改為以 send_time 為 GSI 的 Query 以提升效率。
    回傳符合條件的訂閱清單，每筆包含 id、user_id、channel_url、recipient_email、
    audio_speed、send_time、is_active 等欄位。
    """
    subscriptions_table = config.get_subscriptions_table()
    current_time = get_current_utc_hhmm()

    logger.info(f"查詢 UTC 時間 {current_time} 的到期訂閱")

    table = _dynamodb.Table(subscriptions_table)

    # 共用 Scan 參數，避免在分頁迴圈中重複撰寫相同過濾條件
    scan_kwargs: dict[str, Any] = {
        "FilterExpression": "is_active = :active AND send_time = :time",
        "ExpressionAttributeValues": {
            ":active": True,
            ":time": current_time,
        },
    }

    try:
        items: list[dict[str, Any]] = []

        # 處理 DynamoDB 分頁（單次 Scan 最多回傳 1MB 資料）
        while True:
            response = table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        logger.info(f"查詢到 {len(items)} 個到期訂閱")
        return items

    except Exception as e:
        logger.error(f"查詢訂閱時發生錯誤：{e}", exc_info=True)
        raise
