# DynamoDB IAM 權限設計：GSI Query 需要獨立 ARN

**日期**：2026-05-03
**類型**：技術決策 / 問題排除 / 風險記錄

---

## 發生了什麼

`yt-to-mail-scheduler` 排程執行後，同一部影片在短時間內重複寄送給同一用戶（確認有三次重複紀錄）。

DynamoDB Console 可以看到 `yt-to-mail-history` 表內資料寫入正常，PutItem 沒有問題。但 `get_sent_video_ids()` 每次執行都拿到空 set，導致去重邏輯完全失效。

Lambda / EC2 執行 log 中可見：

```
AccessDeniedException: User: arn:aws:iam::{account}:user/yt-to-mail-scheduler
is not authorized to perform: dynamodb:Query
on resource: arn:aws:dynamodb:{region}:{account}:table/yt-to-mail-history/index/user_id-index
```

---

## 根本原因

### DynamoDB 的三種讀取方式與對應 IAM Action

| 操作 | IAM Action | 說明 |
|------|-----------|------|
| 用主鍵（Partition Key）取一筆 | `dynamodb:GetItem` | 精確命中，最快 |
| 在 base table 或 GSI 上查一個 PK 的所有資料 | `dynamodb:Query` | 需指定 PK 值 |
| 掃描整張表 | `dynamodb:Scan` | 全表走訪，成本高 |

### GSI 是什麼

Global Secondary Index（全域次要索引）：讓你用「非主鍵欄位」做 `Query` 的機制。

`yt-to-mail-history` 表的主鍵是 `id`（UUID），但程式需要用 `user_id` 查「這個用戶寄過哪些影片」，所以建了 GSI `user_id-index`（以 `user_id` 為 Partition Key）。

### IAM Resource ARN 有兩種層級

AWS IAM 對 DynamoDB 的 resource 分兩種，意義完全不同：

```
# base table ARN — 授權對 table 本身的操作（PutItem、GetItem、base table Query...）
arn:aws:dynamodb:{region}:{account}:table/{TableName}

# GSI ARN — 授權對 GSI 的操作（在 GSI 上執行 Query）
arn:aws:dynamodb:{region}:{account}:table/{TableName}/index/*
```

**核心規則**：`dynamodb:Query` 在 GSI 上執行時，IAM 驗證的是 **GSI ARN**，不是 base table ARN。

兩個 ARN 在 IAM 是獨立的授權對象，缺一不可。

### 這次的實際缺陷

`yt-to-mail-scheduler` IAM User 的 `WriteReadHistory` PolicyStatement 只列了 base table ARN：

```typescript
// 錯誤寫法（缺 GSI ARN）
new iam.PolicyStatement({
  actions: ['dynamodb:PutItem', 'dynamodb:Query'],
  resources: [
    `arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-history`,
    // 漏掉了 index/* ARN
  ],
})
```

`dynamodb:Query` + base table ARN 只能授權「對 base table 做 Query」。對 `user_id-index` 做 Query 走的是 GSI ARN，policy 裡沒有 → AccessDeniedException。

---

## 解法

在 `resources` 陣列補上 `index/*` ARN：

```typescript
// 正確寫法（含 GSI ARN）
new iam.PolicyStatement({
  actions: ['dynamodb:PutItem', 'dynamodb:Query'],
  resources: [
    `arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-history`,
    `arn:aws:dynamodb:${region}:${account}:table/yt-to-mail-history/index/*`,
  ],
})
```

`index/*` 是萬用字元，涵蓋這張表上所有 GSI。若需要更細粒度控管，可以改寫成 `index/user_id-index` 只授權特定 GSI。

---

## 為何這個錯誤難以發現

### 1. PutItem 正常，表面上功能沒壞

base table ARN 已授權 `dynamodb:PutItem`，歷史記錄寫入成功。DynamoDB Console 看得到資料，scheduler 沒有拋出寫入錯誤，一切看起來正常運作。

### 2. Query 失敗靜默吞掉，fallback 回空 set

`get_sent_video_ids()` 通常長這樣：

```python
def get_sent_video_ids(user_id: str) -> set:
    try:
        response = dynamodb.query(
            TableName='yt-to-mail-history',
            IndexName='user_id-index',
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': {'S': user_id}},
        )
        return {item['video_id']['S'] for item in response['Items']}
    except Exception:
        return set()   # AccessDeniedException 被吞掉，回傳空 set
```

caller 拿到空 set，認為「此用戶從未寄過任何影片」，繼續執行寄信流程。程式不會崩潰，log 裡不會有 ERROR，表面完全正常。

（若有記 exception log，會看到 AccessDeniedException，但不是所有專案都把 except 的例外記下來。）

### 3. CDK 部署不驗證 IAM 充分性

`cdk synth` 和 `cdk deploy` 只驗證 CloudFormation 範本格式是否合法，不會驗證 IAM policy 是否「足夠」讓程式碼跑起來。缺 GSI ARN 不是格式錯誤，所以部署全程無任何警告。

### 4. 症狀與根因距離兩層

```
症狀：重複寄信
  └─ 原因：去重邏輯沒發揮作用（get_sent_video_ids 回傳空 set）
       └─ 根因：IAM 缺 GSI ARN → AccessDeniedException → except 吞掉
```

從「重複寄信」直觀聯想到「IAM 權限不足」需要跨越兩層間接，除錯過程極容易在第一層（去重邏輯）打轉。

---

## 風險與注意事項

### 規劃 IAM 時的必問清單（給 cdk-arch）

1. **這個資料存取是 GetItem 還是 Query？**
   - GetItem → 只需要 base table ARN
   - Query → 確認是走 base table 還是 GSI

2. **如果走 GSI，`resources` 有沒有列 `index/*` ARN？**
   - 每一個 Query on GSI 都需要對應的 `index/` ARN

3. **有沒有新的讀取路徑在規格裡但 IAM 沒更新？**
   - 功能迭代時新增 GSI Query，舊的 PolicyStatement 不會自動更新

### 快速驗證方法

**方法一：看 CloudWatch / 應用程式 log**

搜尋 `AccessDeniedException` 關鍵字。若有，幾乎可以確定是 IAM 問題，錯誤訊息會直接告訴你缺的是哪個 resource ARN。

**方法二：AWS Console IAM Policy Simulator**

1. AWS Console → IAM → Users → 找到對應 User
2. 左側 Permissions → 展開 inline policy
3. 右上角 Simulate → 選 `dynamodb:Query`
4. Resource 填入 GSI ARN（`arn:aws:dynamodb:...:table/{TableName}/index/{IndexName}`）
5. 執行模擬，看結果是 Allow 還是Deny

**方法三：直接在 DynamoDB Console 手動跑 Query**

用對應 IAM 的 credentials，在 Console 的 PartiQL editor 執行：

```sql
SELECT * FROM "yt-to-mail-history"."user_id-index"
WHERE user_id = 'test-user-id'
```

若出現 AccessDeniedException，確認是 IAM 問題。

---

## 參考資料

- [AWS 文件：DynamoDB 的 IAM Actions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/api-permissions-reference.html)
- [AWS 文件：Using IAM with DynamoDB Global Secondary Indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/access-control-overview.html)
- [AWS CDK：iam.PolicyStatement API](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_iam.PolicyStatement.html)
