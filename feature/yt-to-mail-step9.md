# yt-to-mail-step9：Phase 4 — 部署（S3 + CloudFront）

## 功能名稱

前端靜態網站部署：S3 + CloudFront + Lambda CORS 更新

---

## 目標

將 Phase 3 建立的 React 前端靜態檔案部署至 AWS，透過 CloudFront CDN 對外提供服務：
1. 建立 S3 Bucket 存放靜態檔案（封鎖公開存取）
2. 建立 CloudFront Distribution，以 OAC 存取 S3
3. 設定 SPA 路由支援（自訂錯誤頁回傳 index.html）
4. 設定分層快取策略（HTML 不快取、靜態資源長快取）
5. 前端 build 並上傳 S3
6. 取得 CloudFront 網域後，回頭更新 Lambda Function URL 的 CORS AllowOrigins

---

## 技術規格

### AWS 服務與資源

#### S3 Bucket（前端靜態檔案）

- Bucket 名稱：`yt-to-mail-frontend-<account-id>`（含 account-id 避免命名衝突）
- 區域：與 Lambda 相同 Region
- 公開存取：**全部封鎖**（Block All Public Access = true）
- 版本控制：**停用**（原型階段，不需要版本回滾）
- 靜態網站代管：**停用**（使用 CloudFront + OAC，不需 S3 靜態網站功能）
- 刪除政策：`RemovalPolicy.DESTROY`（原型方便清理）
- Auto Delete Objects：`true`（CDK 清除時自動刪除）

**Bucket Policy**：
- 僅允許 CloudFront OAC 服務主體讀取（`s3:GetObject`）
- 禁止任何直接公開存取

---

#### CloudFront Distribution

- 來源（Origin）：S3 Bucket
- 存取控制：OAC（Origin Access Control），不使用舊版 OAI
  - OAC 名稱：`yt-to-mail-frontend-oac`
  - 簽署協定：`sigv4`
  - 簽署行為：`always`
- 網域：使用 CloudFront 預設網域（`.cloudfront.net`），不設定自訂域名
- HTTPS：強制 HTTPS（HTTP 自動重導至 HTTPS）
- HTTP 版本：`HTTP2`
- 地理限制：無

**快取策略（分層設定）**：

**Layer 1：index.html 及其他 HTML 檔案**
- 路徑模式：`*.html`
- 快取行為：`Cache-Control: no-cache, no-store, must-revalidate`
- TTL：min=0, default=0, max=0（不快取，確保部署後立即生效）

**Layer 2：靜態資源（JS / CSS / 圖片等）**
- 路徑模式：`Default (*)`
- 快取行為：Vite build 預設為靜態資源加入 content hash（例如 `main.a1b2c3.js`），可長期快取
- TTL：min=0, default=86400（1 天）, max=31536000（1 年）
- `Cache-Control: public, max-age=31536000, immutable`（由 S3 上傳時設定 metadata）

**自訂錯誤頁面（SPA 路由支援）**：
- 錯誤碼 403（S3 回傳，因路徑不存在）→ 回應路徑 `/index.html`，HTTP 狀態碼改為 `200`
- 錯誤碼 404 → 回應路徑 `/index.html`，HTTP 狀態碼改為 `200`

> 說明：React Router 的 SPA 路由（如 `/subscriptions/add`）在 CloudFront 找不到對應 S3 物件時會觸發 403/404，將其重導至 index.html 後由 React Router 接管路由即可正常運作。

---

### CDK Stack 結構

- Stack 名稱：`YtToMailFrontendStack`
- 檔案位置：`lib/yt-to-mail-frontend-stack.ts`
- Construct 層次：
  ```
  YtToMailFrontendStack
  ├── S3 Bucket: yt-to-mail-frontend-<account-id>
  ├── CloudFront OAC: yt-to-mail-frontend-oac
  ├── CloudFront Distribution
  │     ├── Origin: S3 Bucket（透過 OAC）
  │     ├── DefaultBehavior: 靜態資源長快取
  │     ├── AdditionalBehavior: *.html 不快取
  │     └── CustomErrorResponses: 403/404 → /index.html (200)
  ├── BucketDeployment: 自動上傳 frontend/dist/ 並觸發 CloudFront Invalidation
  └── CfnOutput: CloudFrontDomain、CloudFrontUrl、S3BucketName、CloudFrontDistributionId
  ```

**與 YtToMailBackendStack 的依賴關係**：
- `YtToMailFrontendStack` 部署完成後，需取得 CloudFront 網域
- 手動（或以 CDK 參數）更新 `YtToMailBackendStack` Lambda Function URL 的 CORS AllowOrigins

---

### Lambda CORS 更新規格

Phase 4 部署完成後，`YtToMailBackendStack` 中 Lambda Function URL 的 CORS 設定需從：
```
AllowOrigins: ["*"]
```
改為：
```
AllowOrigins: ["https://<cloudfront-domain>.cloudfront.net"]
```

**更新方式**（CDK 參數化）：
- 在 `YtToMailBackendStack` 的 `props` 中加入 `allowedOrigin: string` 參數
- 預設值為 `"*"`（Phase 1 初始部署使用）
- Phase 4 完成後，以 `cdk deploy YtToMailBackendStack --context allowedOrigin=https://xxx.cloudfront.net` 重新部署

---

### 前端 Build 與部署流程

**Step 1：設定生產環境變數**

在 `frontend/.env.production` 填入 Lambda Function URL：
```
VITE_API_BASE_URL=https://xxxxx.lambda-url.ap-northeast-1.on.aws
```

**Step 2：執行 build**

```powershell
cd frontend
npm run build
# 產出 dist/ 目錄
```

**Step 3：cdk deploy 自動上傳 + CloudFront Invalidation**

`YtToMailFrontendStack` 已透過 CDK `BucketDeployment` 整合上傳與快取清除：
```powershell
npx cdk deploy YtToMailFrontendStack
```

- CDK 部署時自動將 `frontend/dist/` 同步至 S3（透過 Lambda 自訂資源）
- 部署完成後自動觸發 CloudFront Invalidation（`/*`），無需手動執行 `aws cloudfront create-invalidation`

> **注意**：每次修改前端程式碼後，需先重新執行 `npm run build` 再 `cdk deploy`，因為 CDK 上傳的是 `dist/` 目錄的靜態產出。

---

### IAM 部署權限說明

CDK 部署需要本機 AWS CLI 設定的帳號具備：
- `s3:PutObject`、`s3:DeleteObject`、`s3:GetObject`（S3 操作）
- `cloudfront:CreateDistribution`、`cloudfront:UpdateDistribution`（CloudFront 操作）
- `lambda:UpdateFunctionConfiguration`（更新 Lambda CORS）
- `iam:CreateRole`、`iam:PutRolePolicy`（IAM 操作）

CDK Bootstrap 需預先執行（首次部署）：
```powershell
npx cdk bootstrap aws://<account-id>/<region>
```

---

### CfnOutput 規格

| Output 名稱 | 說明 |
|---|---|
| `CloudFrontDomain` | CloudFront 網域（不含 https://）|
| `CloudFrontUrl` | 完整前端 URL（https:// 開頭）|
| `S3BucketName` | S3 Bucket 名稱（供 CLI 上傳使用）|
| `CloudFrontDistributionId` | Distribution ID（供 Invalidation 使用）|

---

## 實作步驟（供 cdk-coder 執行）

- Step 1：建立 CDK Stack `YtToMailFrontendStack`（`lib/yt-to-mail-frontend-stack.ts`）
- Step 2：建立 S3 Bucket，設定封鎖公開存取、RemovalPolicy.DESTROY、autoDeleteObjects
- Step 3：建立 CloudFront OAC（`CfnOriginAccessControl`）
- Step 4：設定 S3 Bucket Policy，允許 CloudFront OAC 的 `s3:GetObject`
- Step 5：建立 CloudFront Distribution，設定 OAC 來源、HTTPS 強制
- Step 6：設定 DefaultBehavior 快取（靜態資源長快取）
- Step 7：新增 `*.html` AdditionalBehavior（不快取）
- Step 8：設定 CustomErrorResponses（403 → /index.html 200，404 → /index.html 200）
- Step 9：更新 `YtToMailBackendStack`，`props` 加入 `allowedOrigin: string` 參數（預設 `"*"`）
- Step 10：更新 Lambda Function URL CORS 設定，使用 `allowedOrigin` 參數
- Step 11：新增四個 `CfnOutput`（CloudFrontDomain、CloudFrontUrl、S3BucketName、CloudFrontDistributionId）
- Step 12：加入 `BucketDeployment`，自動上傳 `frontend/dist/` 至 S3 並觸發 CloudFront Invalidation
- Step 13：更新 `bin/` 入口，將 `YtToMailFrontendStack` 加入部署清單
- Step 14：提供部署指令說明文件（build → cdk deploy → CORS 更新步驟）

---

## 驗收標準

- [ ] `cdk synth` 無錯誤，產出 S3 Bucket、CloudFront Distribution
- [ ] S3 Bucket 封鎖所有公開存取，無法直接以 S3 URL 存取物件
- [ ] CloudFront Distribution 使用 OAC 存取 S3（非 OAI）
- [ ] `https://<cloudfront-domain>/` 可正常載入前端首頁
- [ ] 直接存取 `https://<cloudfront-domain>/subscriptions/add` 不出現 403/404，正常載入 React 頁面
- [ ] 靜態資源（JS/CSS）的 Cache-Control 為長期快取（max-age=31536000）
- [ ] index.html 的 Cache-Control 為 no-cache
- [ ] `npm run build` + `cdk deploy YtToMailFrontendStack` 可完成上傳與 CloudFront Invalidation（無需手動 aws cli）
- [ ] Lambda Function URL CORS AllowOrigins 更新為 CloudFront 網域後，前端 API 呼叫正常（無 CORS 錯誤）
- [ ] `cdk deploy YtToMailFrontendStack` 成功，輸出 CloudFront 網域

---

## 注意事項與限制

- CloudFront 使用預設 `.cloudfront.net` 網域，不設定 ACM 憑證或自訂域名（原型階段）
- OAC 為較新的 S3 存取控制機制，須使用 `CfnOriginAccessControl`（L1 Construct），CDK L2 的 `Distribution` 尚未完整支援 OAC，需手動設定 Bucket Policy 的 `aws:SourceArn` 條件
- S3 上傳需分兩次執行（HTML 與非 HTML），因 `Cache-Control` 設定不同
- `autoDeleteObjects` 需要 CDK 在 S3 Bucket 上部署 Lambda 自訂資源（清除時自動刪除物件），會產生額外的 Lambda 資源，原型可接受
- CloudFront Distribution 建立約需 5～15 分鐘，`cdk deploy` 會等待部署完成
- Lambda CORS 更新需重新執行 `cdk deploy YtToMailBackendStack`，CloudFront 不需重新部署
- 所有函式必須包含繁體中文函式級註解
