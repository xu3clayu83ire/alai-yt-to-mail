import logging
import sys
import config
import dynamo_reader
import processor

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
    format="[%(asctime)s] %(levelname)s %(message)s")

subs = dynamo_reader._dynamodb.Table(config.get_subscriptions_table()).scan()["Items"]
print(f"找到 {len(subs)} 筆訂閱")

if subs:
    result = processor.process_subscription(subs[0])
    print(f"結果：{result}")
else:
    print("DynamoDB 無訂閱資料")
