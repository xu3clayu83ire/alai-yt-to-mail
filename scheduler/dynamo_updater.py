"""
dynamo_updater.py — DynamoDB 訂閱欄位更新模組

集中管理排程器對 subscriptions 資料表的寫入操作。
將 UpdateItem 與 DeleteItem 邏輯獨立為此模組，
確保 processor.py 只需關注業務流程，不直接操作 DynamoDB 細節。
"""

import logging
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

import config

logger = logging.getLogger(__name__)

# 建立 DynamoDB resource（使用 config 中的 Region）
_dynamodb = boto3.resource("dynamodb", region_name=config.get_aws_region())


def _get_subscriptions_table():  # type: ignore[return]  # boto3 Table 無公開型別存根
    """
    取得 subscriptions DynamoDB Table resource 物件。
    使用延遲取得以確保 config 已完整載入。
    """
    return _dynamodb.Table(config.get_subscriptions_table())


def reset_no_new_video_days(subscription_id: str) -> None:
    """
    將指定訂閱的 no_new_video_days 欄位重置為 0。
    當 status=done（頻道有新影片且成功寄信）時呼叫，
    確保計數器不會因為偶發的有新影片而被跳過清零。
    失敗時記錄 WARNING 但不拋出例外，避免中斷主流程。
    """
    try:
        table = _get_subscriptions_table()
        table.update_item(
            Key={"id": subscription_id},
            UpdateExpression="SET no_new_video_days = :zero",
            ExpressionAttributeValues={":zero": Decimal("0")},
        )
        logger.debug(f"[sub:{subscription_id}] no_new_video_days 已重置為 0")
    except Exception as e:
        logger.warning(
            f"[sub:{subscription_id}] 重置 no_new_video_days 失敗（忽略）：{e}",
            exc_info=True,
        )


def increment_no_new_video_days(subscription_id: str) -> int:
    """
    將指定訂閱的 no_new_video_days 欄位原子性加 1，回傳更新後的值。
    使用 DynamoDB ADD 原子操作確保多次並行執行不會產生競爭條件。
    欄位不存在時（例如舊有資料尚未建立此欄位），ADD 會從 0 開始累加，
    自動初始化為 1，無需額外的讀取再寫入操作。
    發生任何例外時回傳 -1，讓呼叫端決定是否觸發自動取消邏輯。
    """
    try:
        table = _get_subscriptions_table()
        response = table.update_item(
            Key={"id": subscription_id},
            UpdateExpression="ADD no_new_video_days :inc",
            ExpressionAttributeValues={":inc": Decimal("1")},
            ReturnValues="UPDATED_NEW",
        )
        updated_value = int(response["Attributes"]["no_new_video_days"])
        logger.debug(f"[sub:{subscription_id}] no_new_video_days 更新為 {updated_value}")
        return updated_value
    except Exception as e:
        logger.error(
            f"[sub:{subscription_id}] 累加 no_new_video_days 失敗：{e}",
            exc_info=True,
        )
        return -1


def delete_subscription(subscription_id: str) -> None:
    """
    刪除指定訂閱記錄（自動取消時呼叫）。
    與 reset/increment 不同，刪除失敗代表自動取消流程未完成，
    因此拋出例外讓呼叫端決定後續處理方式（例如記錄錯誤但不重試）。
    """
    try:
        table = _get_subscriptions_table()
        table.delete_item(Key={"id": subscription_id})
        logger.info(f"[sub:{subscription_id}] 訂閱已刪除（自動取消）")
    except Exception as e:
        logger.error(
            f"[sub:{subscription_id}] 刪除訂閱失敗：{e}",
            exc_info=True,
        )
        raise
