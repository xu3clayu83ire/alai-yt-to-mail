# yt-to-mail v2 開發進度

**版本**：2.0  
**最後更新**：2026-05-03

---

## CDK 基礎設施（step6 新增）

### CDK 專案初始化
- [x] 建立 `package.json`、`tsconfig.json`、`cdk.json`、`jest.config.js`
- [x] 安裝 aws-cdk-lib、constructs 等 npm 依賴套件
- [x] 建立 `bin/yt-to-mail.ts` CDK 入口點

### CDK Stack（Step 1-4, 15-16）
- [x] Step 1：建立三張 DynamoDB 資料表（users、subscriptions、history）及各自 GSI
- [x] Step 2：建立 IAM 執行角色（最小權限，yt-to-mail-* 表）
- [x] Step 3：建立 Lambda Function（python3.12、512MB、30s timeout、環境變數）
- [x] Step 4：啟用 Lambda Function URL（AuthType NONE、CORS AllowOrigins *）
- [x] Step 15：CDK bundling（部署前自動 pip install）
- [x] Step 16：CfnOutput 輸出 Function URL

### Lambda Python 應用程式（Step 5-14）
- [x] Step 5：建立 `lambda/api/` 目錄，撰寫 `requirements.txt`
- [x] Step 6：實作 `main.py`（FastAPI + Mangum）
- [x] Step 7：實作 `services/auth_service.py`（bcrypt、JWT）
- [x] Step 8：實作 `services/dynamo_service.py`（DynamoDB CRUD）
- [x] Step 9：實作 `dependencies.py`（get_current_user）
- [x] Step 10：實作 `routers/auth.py`（register / login）
- [x] Step 11：實作 `routers/subscriptions.py`（CRUD + 上限驗證）
- [x] Step 12：實作 `routers/history.py`（GET + limit/subscription_id）
- [x] Step 13：實作 `routers/channels.py`（URL 解析）
- [x] Step 14：實作 Pydantic 模型（user.py、subscription.py、history.py）

### CDK 測試
- [x] 建立 `test/yt-to-mail-backend-stack.test.ts`

---

## Phase 1：雲端後端（Lambda + DynamoDB）

### DynamoDB 資料表建立
- [x] 建立 `users` 資料表（PK: id, GSI: email-index）
- [x] 建立 `subscriptions` 資料表（PK: id, GSI: user_id-index）
- [x] 建立 `history` 資料表（PK: id, GSI: user_id-index）

### Lambda + FastAPI 應用程式
- [x] 初始化 Python 專案結構（lambda/api/）
- [x] 安裝依賴套件（fastapi、mangum、boto3、python-jose、bcrypt）
- [x] 建立 FastAPI 主應用程式入口（main.py）
- [x] 建立 Mangum 封裝（Lambda handler）

### 認證路由
- [x] 實作 `POST /auth/register`（email 驗重、bcrypt 雜湊、寫入 DynamoDB）
- [x] 實作 `POST /auth/login`（驗證密碼、回傳 JWT）
- [x] 實作 JWT 中介層（Bearer token 驗證）
- [x] 設定 JWT secret key 環境變數

### 訂閱 CRUD 路由
- [x] 實作 `GET /subscriptions`（取得用戶訂閱列表）
- [x] 實作 `POST /subscriptions`（新增訂閱，含上限 5 個驗證）
- [x] 實作 `PUT /subscriptions/{id}`（修改訂閱，含擁有者驗證）
- [x] 實作 `DELETE /subscriptions/{id}`（刪除訂閱，含擁有者驗證）

### 歷史紀錄路由
- [x] 實作 `GET /history`（取得用戶歷史紀錄，依 sent_at 降冪排序）

### Lambda 部署設定
- [x] 建立 IAM 執行角色（DynamoDB 讀寫權限）
- [x] 建立 Lambda Function（Python 3.12 Runtime）
- [x] 設定 Lambda 環境變數（JWT_SECRET_KEY、USERS_TABLE、SUBSCRIPTIONS_TABLE、HISTORY_TABLE）
- [x] 啟用 Lambda Function URL（CORS 設定）
- [x] CDK bundling 自動打包依賴套件

### Phase 1 驗收測試
- [x] cdk-tester 執行 tsc + jest + cdk synth 驗證通過（12/12 測試全過，exit code 0）
- [ ] 使用 curl / Postman 驗證所有 API 端點（部署後）
- [ ] 確認 DynamoDB 資料正確寫入（部署後）

---

## Phase 2：本機排程整合

### IAM 設定
- [x] 建立 IAM User（yt-to-mail-scheduler）- 在 CDK Stack 中以 CfnAccessKey 建立
- [x] 設定 IAM Policy（yt-to-mail-scheduler-policy，subscriptions 讀 + history 寫，最小權限）
- [x] CfnOutput 輸出 Access Key ID 與 Secret Access Key 供本機 aws configure 設定

### 本機排程腳本
- [x] 建立 scheduler/ 目錄結構（含 logs/）
- [x] 建立 requirements.txt（boto3、python-dotenv、openai-whisper、yt-dlp、google-api-python-client、google-auth-oauthlib）
- [x] 實作 config.py（python-dotenv 讀取 .env，提供所有設定函式）
- [x] 實作 dynamo_reader.py（UTC 時間取得、Scan subscriptions 表、分頁處理）
- [x] 實作 processor.py（yt-dlp 取清單 → 篩選 ≤60s → 下載 → 速度調整 → Whisper → 語言判斷 → Gmail 寄信 → 暫存清理）
- [x] 實作 gmail_sender.py（OAuth2 認證、純文字+HTML 雙版本、mp3 附件）
- [x] 實作 history_writer.py（PutItem 寫入 history 表，含 error_message 截斷）
- [x] 實作 run.py（主入口、TimedRotatingFileHandler、個別 try/except）
- [x] 建立 .env.example 範本
- [x] 建立 scheduler/README.md（含 Windows 工作排程器 PowerShell 指令）

### Windows 工作排程器設定
- [ ] 本機執行 PowerShell 指令建立排程工作（需本機操作）
- [ ] 測試排程器正確觸發（需部署後驗證）

### Phase 2 驗收測試
- [ ] 手動執行腳本，確認端到端流程正常（需部署後驗證）
- [ ] 確認 history 表正確記錄結果（需部署後驗證）
- [ ] 確認非英文影片被正確跳過並記錄 skipped_language（需部署後驗證）

---

## Phase 3：前端（React）

### 專案初始化
- [x] 使用 Vite 建立 React + TypeScript 專案
- [x] 安裝依賴套件（react-router-dom、axios、react-hook-form、zod、@hookform/resolvers、@tanstack/react-query）
- [x] 設定 API base URL 環境變數（.env / .env.production）
- [x] 設定 axios 攔截器（JWT 自動附加 Authorization header）

### 頁面實作
- [x] 建立登入頁面（LoginPage）
- [x] 建立註冊頁面（RegisterPage）
- [x] 建立訂閱列表頁面（SubscriptionListPage）
- [x] 建立新增訂閱頁面（AddSubscriptionPage，含頻道確認兩步驟流程）
- [x] 建立編輯訂閱頁面（EditSubscriptionPage）
- [x] 建立歷史紀錄頁面（HistoryPage）

### 元件與功能
- [x] 建立路由守衛（ProtectedRoute，未登入導向 /login）
- [x] 實作 JWT 存放邏輯（localStorage storage.ts）
- [x] 實作時區換算（utils/timezone.ts：本地時間 ↔ UTC）
- [x] 實作訂閱啟用/停用切換（SubscriptionCard + PUT API）
- [x] 建立共用版面元件（Layout.tsx：Header + Nav + 登出按鈕）
- [x] 建立歷史紀錄項目元件（HistoryItem.tsx：狀態標籤顏色）

### Phase 3 驗收測試
- [x] npm run build 無 TypeScript 錯誤，產生 dist/ 靜態檔案
- [ ] 本機開發伺服器（npm run dev）正常運行（需本機驗證）
- [ ] 所有頁面路由正確（需本機驗證）
- [ ] 登入/登出流程正常（需部署後驗證）
- [ ] 訂閱 CRUD 操作正常（需部署後驗證）

---

## Phase 4：部署

### S3 設定
- [x] 建立 S3 bucket（yt-to-mail-frontend-<account-id>，封鎖公開存取）
- [x] 設定 Bucket Policy（限制只允許 CloudFront OAC 服務主體存取，含 aws:SourceArn 條件）
- [x] RemovalPolicy.DESTROY + autoDeleteObjects（原型階段方便清理）

### CloudFront 設定
- [x] 建立 CloudFront OAC（CfnOriginAccessControl，sigv4 + always）
- [x] 建立 CloudFront Distribution（L2 + addPropertyOverride 手動設定 OAC ID）
- [x] 設定預設根物件（index.html）
- [x] 設定 defaultBehavior：CachingOptimized（靜態資源長期快取）
- [x] 設定 additionalBehaviors：*.html 使用 CachingDisabled（TTL=0）
- [x] 設定 SPA 路由錯誤頁面（403/404 → /index.html，HTTP 狀態碼 200）
- [x] 設定四個 CfnOutput（CloudFrontDomain、CloudFrontUrl、S3BucketName、CloudFrontDistributionId）

### Backend CORS 參數化
- [x] YtToMailBackendStackProps 加入 allowedOrigin 參數（預設 "*"）
- [x] Lambda Function URL CORS allowedOrigins 改用 allowedOrigin 參數
- [x] bin/yt-to-mail.ts 加入 YtToMailFrontendStack，從 CDK Context 讀取 allowedOrigin
- [x] cdk synth 驗證通過（YtToMailBackendStack + YtToMailFrontendStack）
- [x] tsconfig.json exclude 加入 "frontend"（避免 CDK tsc 誤掃 React 原始碼）
- [x] cdk-tester 驗證通過（tsc noEmit + Jest 12/12 + cdk synth）

### 前端部署
- [ ] 設定 .env.production（API base URL 指向 Lambda Function URL）
- [ ] 執行 `npm run build` 產生靜態檔案
- [ ] 上傳 dist/ 到 S3 bucket
- [ ] 建立 CloudFront Invalidation（清除快取）

### Phase 4 驗收測試
- [ ] 透過 CloudFront 網址正常存取前端
- [ ] SPA 路由重整不出現 403/404
- [ ] 前端可成功呼叫 Lambda API

---

## 文件階段（所有 Phase 完成後）
- [ ] doc-master 更新 README.md（含架構說明）
- [ ] doc-master 建立 docs/phase1-cloud-backend.md
- [ ] doc-master 建立 docs/phase2-local-scheduler.md
- [ ] doc-master 建立 docs/phase3-frontend.md
- [ ] doc-master 建立 docs/phase4-deployment.md
- [ ] doc-master 更新 CHANGELOG.md

---

# yt-to-mail v3 開發進度

**版本**：3.0
**最後更新**：2026-05-03

---

## Phase 5：公開訂閱 API + 前端公開頁（step10, step12, step13）

### step10：後端公開訂閱 API（Coder A，可立即開始）✅ 已完成
- [x] 新增 `lambda/api/routers/public.py`（POST /public/subscribe, GET/DELETE /public/subscriptions）
- [x] 修改 `lambda/api/models/subscription.py`（新增 PublicSubscriptionCreate, PublicSubscriptionResponse, auto_cancel_days / no_new_video_days 欄位）
- [x] 修改 `lambda/api/main.py`（掛載 public router）
- [x] 驗證：`POST /public/subscribe` 上限 5 個、`GET` 以 email 查詢、`DELETE` email 驗證
- [x] cdk-tester 通過（tsc + jest + cdk synth）

### step12：前端公開訂閱頁（Coder B，待 step10 完成後整合測試）✅ 已完成
- [x] 修改 `frontend/src/App.tsx`（根路由導向 AddSubscriptionPage，調整路由表）
- [x] 修改 `frontend/src/pages/AddSubscriptionPage.tsx`（移除 ProtectedRoute、加入 recipient_email 與 auto_cancel_days 欄位、改呼叫 POST /public/subscribe、送出後顯示成功訊息）
- [x] 新增 `frontend/src/api/public.ts`（publicSubscribe, getPublicSubscriptions, deletePublicSubscription）
- [x] 修改 `frontend/src/types/index.ts`（新增 PublicSubscribeRequest, PublicSubscriptionItem）
- [x] npm run build 無錯誤

### step13：前端 Email 查詢頁（Coder B，可與 step12 平行）✅ 已完成
- [x] 新增 `frontend/src/pages/PublicSubscriptionListPage.tsx`（email 輸入、訂閱清單、無新影片計數、取消訂閱）
- [x] 修改 `frontend/src/App.tsx`（加入 /my-subscriptions 路由）
- [x] npm run build 無 step13 相關 TypeScript 錯誤（剩餘錯誤屬於 step14 AdminRoute/AdminLoginPage/AdminSubscriptionsPage，不在本 step 範疇）

---

## Phase 6：管理員後台（step11, step14）

### step11：後端管理員 API（Coder A，在 step10 後執行）✅ 已完成
- [x] 修改 `lambda/api/routers/auth.py`（login 加入 admin 判斷分支）
- [x] 修改 `lambda/api/services/auth_service.py`（create_access_token 加入 is_admin 參數）
- [x] 修改 `lambda/api/dependencies.py`（新增 get_current_admin）
- [x] 新增 `lambda/api/routers/admin.py`（GET/DELETE /admin/subscriptions）
- [x] 新增 `lambda/api/services/dynamo_service.py` 中的 scan_table 函式
- [x] 修改 `lambda/api/models/subscription.py`（新增 AdminSubscriptionResponse）
- [x] 修改 `lambda/api/main.py`（掛載 admin router）
- [x] 修改 `lib/yt-to-mail-backend-stack.ts`（加入 ADMIN_EMAIL、ADMIN_PASSWORD_HASH 環境變數）
- [x] 修改 `bin/yt-to-mail.ts`（從 CDK Context 讀取 adminEmail、adminPasswordHash）
- [x] cdk-tester 通過（tsc + jest + cdk synth）

### step14：前端管理員後台（任一 Coder，待 step11 後）✅ 已完成
- [x] 新增 `frontend/src/pages/AdminLoginPage.tsx`
- [x] 新增 `frontend/src/pages/AdminSubscriptionsPage.tsx`（全表查詢、email 篩選、取消訂閱）
- [x] 新增 `frontend/src/api/admin.ts`（adminListSubscriptions, adminDeleteSubscription）
- [x] 新增 `frontend/src/components/AdminRoute.tsx`（admin token 守衛）
- [x] 修改 `frontend/src/utils/storage.ts`（getAdminToken, setAdminToken, removeAdminToken）
- [x] 修改 `frontend/src/App.tsx`（加入 /admin/login, /admin/subscriptions 路由）
- [x] npm run build 無錯誤

---

## Phase 7：排程器自動取消（step15）

### step15：排程器自動取消計數器（Coder B，完全獨立，可最先開始）✅ 已完成
- [x] 新增 `scheduler/dynamo_updater.py`（reset_no_new_video_days, increment_no_new_video_days, delete_subscription）
- [x] 修改 `scheduler/processor.py`（status=done 重置計數器；status=skipped_duplicate 累加計數器，達上限觸發自動取消）
- [x] 修改 `scheduler/gmail_sender.py`（新增 send_auto_cancel_email）
- [x] 修改 `scheduler/config.py`（新增 get_frontend_url）
- [x] 更新 `scheduler/.env.example`（加入 FRONTEND_URL）
- [x] 修改 `lib/yt-to-mail-backend-stack.ts`（IAM Policy 加入 UpdateItem、DeleteItem 給 subscriptions 表）
- [x] cdk-tester 通過（CDK Stack 修改部分）

---

## 文件階段（v3 完成）
- [x] doc-master 更新 README.md（加入 v3 無帳號訂閱模式說明、API 端點、部署參數）
- [x] doc-master 更新 CHANGELOG.md（v3.0.0 條目）
- [x] doc-master 更新 feature/checklist.md（v3 驗收項目全數標記完成）
- [x] doc-master 更新 feature/todolist.md（step10–step15 標記完成）

---

# yt-to-mail v4 開發進度

**版本**：4.0
**最後更新**：2026-05-03

---

## Phase 8：Shorts 篩選功能（step16）

### step16：URL 解析保留 Shorts 標記 + 排程器 Shorts 播放清單支援

- [ ] 修改 `lambda/api/routers/channels.py`（`_HANDLE_PATTERN` 與 `verify_channel`：保留 `/shorts` 於正規化輸出）
- [ ] 修改 `lambda/api/routers/public.py`（`_parse_channel_url`：與 `channels.py` 邏輯一致，保留 `/shorts`）
- [ ] 修改 `scheduler/processor.py`（`_get_recent_videos`：依 `/shorts` 結尾決定播放清單 URL）

---

# yt-to-mail v5 開發進度

**版本**：5.0
**最後更新**：2026-05-03

---

## Phase 9：管理員頻道白名單（step17, step18）

### step17：CDK 基礎設施 + 後端 API（單一 Coder，依序執行）

#### Step 17-A：CDK 基礎設施
- [x] `lib/yt-to-mail-backend-stack.ts`：新增 `channelsTable`（PK: channel_id）
- [x] `lib/yt-to-mail-backend-stack.ts`：新增 `channel_id-index` GSI 至 subscriptionsTable
- [x] `lib/yt-to-mail-backend-stack.ts`：新增 `CHANNELS_TABLE` Lambda 環境變數
- [x] `lib/yt-to-mail-backend-stack.ts`：IAM Policy resources 補充 `table/yt-to-mail-*/index/*`
- [x] `lib/yt-to-mail-backend-stack.ts`：新增 `ChannelsTableName` CfnOutput

#### Step 17-B：Pydantic Channel 模型
- [x] 新增 `lambda/api/models/channel.py`（ChannelCreate、ChannelUpdate、ChannelResponse、PublicChannelResponse）

#### Step 17-C：管理員頻道 Router
- [x] 新增 `lambda/api/routers/admin_channels.py`（POST /、GET /、PATCH /{channel_id}、DELETE /{channel_id}）
- [x] DELETE 串聯：查 channel_id-index GSI → 寄通知信 → 批次刪訂閱 → 刪頻道

#### Step 17-D：公開頻道端點
- [x] 修改 `lambda/api/routers/public.py`：新增 `GET /channels` 端點（scan channels table）

#### Step 17-E：主程式更新與刪除廢棄檔案
- [x] 修改 `lambda/api/main.py`：移除 channels router import 與掛載，新增 admin_channels router
- [x] 刪除 `lambda/api/routers/channels.py`

#### Step 17-F：郵件通知
- [x] 修改 `scheduler/gmail_sender.py`：新增 `send_admin_removed_email` 函式

#### 驗收
- [x] `cdk synth` 通過
- [x] `tsc --noEmit` 通過
- [x] `jest` 15/15 全數通過（含 channels 資料表、channel_id-index GSI、CHANNELS_TABLE、index/* IAM 驗證）

---

### step18：前端改版（單一 Coder，依序執行）

#### Step 18-A：型別定義
- [x] 修改 `frontend/src/types/index.ts`：新增 PublicChannelItem、ChannelItem、ChannelCreateRequest、ChannelUpdateRequest、ChannelDeleteResponse
- [x] 移除 `frontend/src/types/index.ts`：ChannelVerifyRequest、ChannelVerifyResponse

#### Step 18-B：API 函式層
- [x] 新增 `frontend/src/api/publicChannels.ts`（getPublicChannels）
- [x] 新增 `frontend/src/api/adminChannels.ts`（adminCreateChannel、adminListChannels、adminUpdateChannel、adminDeleteChannel）

#### Step 18-C：AddSubscriptionPage 重寫
- [x] 修改 `frontend/src/pages/AddSubscriptionPage.tsx`：移除步驟 1 URL 輸入 + verify，改為 GET /public/channels 下拉選單

#### Step 18-D：AdminChannelsPage 新增
- [x] 新增 `frontend/src/pages/AdminChannelsPage.tsx`（列出頻道、新增、修改、刪除含確認對話框）
- [x] 修改 `frontend/src/App.tsx`：新增 /admin/channels 路由（AdminRoute 守衛）

#### Step 18-E：刪除廢棄檔案 + 建置驗證
- [x] 刪除 `frontend/src/api/channels.ts`
- [x] `npm run build` 無 TypeScript 錯誤
