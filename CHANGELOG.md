# CHANGELOG

本文件記錄 yt-to-mail 各版本的重要變更。  
版本格式遵循 [語義化版本](https://semver.org/lang/zh-TW/)，日期格式為 YYYY-MM-DD。

---

## [3.0.0] - 2026-05-03

### Added

**後端公開 API（無需登入）**
- 新增 `POST /public/subscribe`：任何人可直接以 email 訂閱頻道，無需帳號，支援 `auto_cancel_days` 設定
- 新增 `GET /public/subscriptions?email=xxx`：以 email 查詢訂閱清單，回傳包含 `no_new_video_days` 計數
- 新增 `DELETE /public/subscriptions/{id}?email=xxx`：以 email 驗證擁有權後取消訂閱
- 訂閱模型新增欄位：`auto_cancel_days`（預設 3）、`no_new_video_days`（預設 0）

**後端管理員 API**
- `POST /auth/login` 新增管理員判斷：以 admin email 登入時，JWT payload 含 `is_admin: true`
- 新增 `GET /admin/subscriptions`：管理員取得全表訂閱資料，支援 `?email=xxx` 篩選
- 新增 `DELETE /admin/subscriptions/{id}`：管理員可刪除任意訂閱
- CDK BackendStack 加入 `ADMIN_EMAIL`、`ADMIN_PASSWORD_HASH` 環境變數，透過 CDK Context 設定

**前端公開訂閱頁**
- 根路由 `/` 改為無需登入即可存取的訂閱表單
- 訂閱表單新增欄位：`recipient_email`（收件信箱）、`auto_cancel_days`（無新影片自動取消天數）
- 新增 `frontend/src/api/public.ts`：封裝公開 API 呼叫（publicSubscribe、getPublicSubscriptions、deletePublicSubscription）
- 訂閱成功後顯示成功訊息與「查看我的訂閱」導覽連結

**前端 Email 查詢頁**
- 新增 `/my-subscriptions` 頁面（PublicSubscriptionListPage）：輸入 email 查詢本人訂閱清單
- 每筆訂閱顯示頻道名稱、發送時間（本地時區）、語速、無新影片計數 vs 自動取消上限
- 提供取消訂閱操作（需確認）

**前端管理員後台**
- 新增 `/admin/login` 頁面（AdminLoginPage）
- 新增 `/admin/subscriptions` 頁面（AdminSubscriptionsPage）：顯示全表訂閱、支援 email 篩選、可取消訂閱
- 新增 `AdminRoute` 路由守衛：無 admin token 時重導至 `/admin/login`
- 新增 `frontend/src/api/admin.ts`：封裝管理員 API 呼叫

**排程器自動取消**
- 新增 `scheduler/dynamo_updater.py`：提供 `reset_no_new_video_days`、`increment_no_new_video_days`（DynamoDB 原子 ADD）、`delete_subscription` 函式
- `processor.py` 計數器邏輯：`status=done` 重置計數，`status=skipped_duplicate` 累加計數，達 `auto_cancel_days` 上限時自動刪除訂閱並寄通知信
- `gmail_sender.py` 新增 `send_auto_cancel_email`：通知信含頻道名稱、累積天數與重新訂閱連結
- `config.py` 新增 `get_frontend_url`，從環境變數 `FRONTEND_URL` 讀取前端網址供通知信使用
- IAM Policy 更新：排程器 IAM User 於 subscriptions 表加入 `dynamodb:UpdateItem`、`dynamodb:DeleteItem` 權限

### Changed

- `SubscriptionResponse` 新增 `auto_cancel_days`、`no_new_video_days` 欄位，向後相容（舊資料以預設值 3 / 0 運作）
- `auth_service.py` `create_access_token` 加入 `is_admin` 參數，影響 JWT payload 內容
- `dependencies.py` 新增 `get_current_admin` 依賴，用於保護管理員路由
- `storage.ts` 新增 `getAdminToken`、`setAdminToken`、`removeAdminToken`，與一般用戶 token 分離管理

---

## [2.0.0] - 2026-05-01

### Added

**雲端後端（Lambda + DynamoDB）**
- AWS CDK TypeScript 專案，部署 DynamoDB（users、subscriptions、history 三張資料表）與 Lambda Function URL
- FastAPI + Mangum 應用程式，提供 REST API
- 用戶認證：`POST /auth/register`、`POST /auth/login`（bcrypt 雜湊 + JWT）
- 訂閱 CRUD：`GET/POST/PUT/DELETE /subscriptions`（最多 5 個訂閱，含擁有者驗證）
- 歷史紀錄：`GET /history`（依 sent_at 降冪排序）
- 頻道驗證：`GET /channels/validate`
- IAM 執行角色（最小權限）

**本機排程器**
- `scheduler/run.py`：主排程入口，TimedRotatingFileHandler 日誌
- `scheduler/processor.py`：yt-dlp 下載 → Whisper 轉錄 → Gmail 寄信完整流程
- `scheduler/gmail_sender.py`：Gmail OAuth2 認證，純文字 + HTML 雙版本 + mp3 附件
- `scheduler/history_writer.py`：寫入 DynamoDB history 表
- `scheduler/dynamo_reader.py`：Scan subscriptions 表並依 UTC 時間篩選
- `scheduler/config.py`：python-dotenv 環境變數管理
- Windows 工作排程器每分鐘觸發

**前端（React）**
- Vite + React 19 + TypeScript SPA
- 登入、註冊、訂閱列表、新增/編輯訂閱、歷史紀錄頁面
- JWT 存放 localStorage，axios 攔截器自動附加 Authorization header
- 時區換算工具（本地時間 ↔ UTC）
- ProtectedRoute 路由守衛

**部署基礎設施**
- S3 + CloudFront（OAC SigV4）靜態前端托管
- SPA 路由錯誤頁面（403/404 → index.html）
- BucketDeployment 自動 CloudFront Invalidation
- CORS 參數化（開發期 `*`，正式部署後限縮至 CloudFront 網域）
