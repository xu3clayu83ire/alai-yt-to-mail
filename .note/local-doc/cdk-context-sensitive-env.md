# CDK Context 寫入 cdk.json — 測試用敏感環境變數管理

**日期**：2026-05-03  
**類型**：技術決策 / 風險記錄

---

## 發生了什麼

每次執行 `cdk deploy` 時，Lambda 的 `ADMIN_EMAIL`、`ADMIN_PASSWORD_HASH`、`JWT_SECRET_KEY` 三個環境變數都會被 CDK 程式碼的預設值（空字串）覆蓋，造成在 AWS Console 手動設定的值被清空。

## 根本原因

CDK Stack 的環境變數是透過 `props?.adminEmail ?? ''` 方式從 CDK Context 讀取，若部署時沒有帶 `--context` 參數，fallback 為空字串，進而覆蓋了手動設定的值。每次 `cdk deploy` 都會重新套用 Stack 定義，Lambda 的環境變數區塊會被完整替換，Console 上的手動修改因此被洗掉。

## 解法

**僅限測試環境**：將測試用的帳號密碼與 JWT secret 寫入 `cdk.json` 的 `context` 區塊，CDK 會自動讀取，無需每次部署帶 `--context` 參數。

```json
"context": {
  "adminEmail": "admin@gmail.com",
  "adminPasswordHash": "$2b$12$...",
  "jwtSecretKey": "...",
  ...
}
```

產生 `adminPasswordHash`（bcrypt）：

```sh
uv run --with bcrypt python -c "import bcrypt; print(bcrypt.hashpw(b'密碼', bcrypt.gensalt(12)).decode())"
```

產生 `jwtSecretKey`（64 字元隨機 hex）：

```python
import secrets
secrets.token_hex(32)
```

## 風險與注意事項

- `cdk.json` 含有敏感資料，**絕對不可推送至 GitHub**，必須加入 `.gitignore`
- 此做法僅為測試便利性，不適用正式環境
- 正式部署前必須移除 `cdk.json` 中的敏感值，改用 AWS Secrets Manager 或 CI/CD pipeline 的 secret 注入機制
- `adminPasswordHash` 為 bcrypt hash，演算法參數（rounds=12）若未來調整，舊 hash 仍可驗證，但新用戶會使用新參數

## 參考資料

- [CDK Context 官方文件](https://docs.aws.amazon.com/cdk/v2/guide/context.html)
- [AWS Secrets Manager 整合 CDK](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_secretsmanager-readme.html)
