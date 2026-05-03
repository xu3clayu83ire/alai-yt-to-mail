"""
DynamoDB 通用操作封裝模組。

使用 boto3 resource 模式（非 client 模式）提供更簡潔的 API，
自動處理 DynamoDB 的 Decimal 型別轉換問題，
並集中管理資源初始化（避免每次請求重複建立連線）。

禁止硬編碼 AWS region，boto3 自動從 Lambda 執行環境讀取。
"""

import os
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

# 使用模組層級的 DynamoDB resource 實例
# Lambda 容器重用時可避免重複建立 boto3 session，提升效能
_dynamodb = boto3.resource("dynamodb")


def _get_table(table_name: str):
    """
    取得 DynamoDB Table resource 物件。
    集中管理 table 實例取得，方便未來替換為快取機制。
    """
    return _dynamodb.Table(table_name)


def put_item(table_name: str, item: dict) -> None:
    """
    寫入一筆資料到指定資料表。

    使用 resource 模式的 put_item，自動處理 Python dict 到
    DynamoDB AttributeValue 的型別轉換，無需手動加 {'S': ...} 等標注。
    """
    table = _get_table(table_name)
    table.put_item(Item=item)


def get_item(table_name: str, key: dict) -> Optional[dict]:
    """
    以主鍵取得一筆資料。

    回傳 dict 或 None（資料不存在時），
    呼叫方無需判斷 DynamoDB 回應格式，直接使用 Python dict。
    """
    table = _get_table(table_name)
    response = table.get_item(Key=key)
    return response.get("Item")


def update_item(
    table_name: str,
    key: dict,
    update_fields: dict,
) -> Optional[dict]:
    """
    以主鍵更新指定欄位，回傳更新後的完整項目。

    動態產生 UpdateExpression 與 ExpressionAttributeValues，
    只更新 update_fields 中提供的欄位，不影響其他欄位。
    回傳 ALL_NEW（更新後的完整項目），方便 API 直接回傳給前端。
    """
    table = _get_table(table_name)

    # 動態建立 UpdateExpression
    set_parts = []
    expr_names: dict[str, str] = {}
    expr_values: dict[str, Any] = {}

    for idx, (field, value) in enumerate(update_fields.items()):
        name_placeholder = f"#f{idx}"
        value_placeholder = f":v{idx}"
        set_parts.append(f"{name_placeholder} = {value_placeholder}")
        expr_names[name_placeholder] = field
        expr_values[value_placeholder] = value

    update_expr = "SET " + ", ".join(set_parts)

    response = table.update_item(
        Key=key,
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return response.get("Attributes")


def delete_item(table_name: str, key: dict) -> None:
    """
    以主鍵刪除一筆資料。
    刪除前應先呼叫 get_item 確認存在，以回傳正確的 404 / 403 狀態碼。
    """
    table = _get_table(table_name)
    table.delete_item(Key=key)


def query_by_index(
    table_name: str,
    index_name: str,
    key_condition: Any,
    filter_expression: Optional[Any] = None,
    limit: Optional[int] = None,
    scan_index_forward: bool = True,
) -> list[dict]:
    """
    以 GSI 查詢資料，支援可選的過濾條件與結果數量限制。

    使用 boto3 Key condition 而非手動組裝 expression string，
    降低 expression 語法錯誤的可能性。
    scan_index_forward=False 可實現時間降冪排序（history 查詢需要）。
    """
    table = _get_table(table_name)

    kwargs: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": key_condition,
        "ScanIndexForward": scan_index_forward,
    }

    if filter_expression is not None:
        kwargs["FilterExpression"] = filter_expression

    if limit is not None:
        kwargs["Limit"] = limit

    response = table.query(**kwargs)
    return response.get("Items", [])


def query_by_gsi_partition(
    table_name: str,
    index_name: str,
    partition_key_name: str,
    partition_key_value: str,
    scan_index_forward: bool = True,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    以 GSI Partition Key 查詢所有符合項目（最常見的查詢模式）。

    封裝 Key().eq() 條件建立，呼叫方只需傳入欄位名稱與值，
    不需手動匯入 boto3.dynamodb.conditions.Key。
    """
    key_condition = Key(partition_key_name).eq(partition_key_value)
    return query_by_index(
        table_name=table_name,
        index_name=index_name,
        key_condition=key_condition,
        scan_index_forward=scan_index_forward,
        limit=limit,
    )


def scan_table(table_name: str) -> list[dict]:
    """
    對 DynamoDB 資料表執行完整 Scan，處理分頁，回傳所有項目。

    DynamoDB Scan 每次最多回傳 1MB 資料，超過時透過 LastEvaluatedKey 分頁。
    此函式自動迴圈直到取得全部資料，確保不因分頁遺漏項目。
    僅限管理員功能使用，小規模資料表效能可接受，
    大規模場景應改用 GSI Query 或 ElasticSearch。
    """
    table = _get_table(table_name)
    items: list[dict] = []
    last_key: Optional[dict] = None

    while True:
        kwargs: dict[str, Any] = {}
        if last_key is not None:
            kwargs["ExclusiveStartKey"] = last_key

        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))

        # LastEvaluatedKey 不存在代表已取得全部資料
        last_key = response.get("LastEvaluatedKey")
        if last_key is None:
            break

    return items
