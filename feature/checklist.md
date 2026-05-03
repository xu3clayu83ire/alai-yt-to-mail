# yt-to-mail v2 驗收清單

**版本**：2.0  
**最後更新**：2026-05-01

---

## Phase 1：雲端後端（Lambda + DynamoDB）

### 功能正確性
- [ ] `POST /auth/register` 成功建立用戶，email 重複時回傳 409
- [ ] `POST /auth/login` 密碼正確時回傳有效 JWT，錯誤時回傳 401
- [ ] JWT token 過期後（24 小時）API 回傳 401
- [ ] `GET /subscriptions` 僅回傳當前用戶的訂閱（不洩漏其他用戶資料）
- [ ] `POST /subscriptions` 第 6 個訂閱回傳 400（超過上限）
- [ ] `PUT /subscriptions/{id}` 修改他人訂閱時回傳 403
- [ ] `DELETE /subscriptions/{id}` 刪除他人訂閱時回傳 403
- [ ] `GET /history` 僅回傳當前用戶的歷史紀錄

### 程式品質
- [ ] pytest 測試全數通過
- [ ] 所有函式具備繁體中文函式級註解
- [ ] 無使用 `any` 型別（Python type hints 正確標注）
- [ ] 無硬編碼的密鑰或 API Key

### 安全性
- [ ] JWT secret key 存放於 Lambda 環境變數（非程式碼）
- [ ] 密碼使用 bcrypt 雜湊儲存（不明文存放）
- [ ] IAM 執行角色遵循最小權限原則（僅限指定三張表的操作）
- [ ] Lambda Function URL CORS 設定正確（開發期允許 *，正式部署後限制 CloudFront）
- [ ] API 路由均需 JWT 驗證（除 /auth/* 外）

### 部署鏈路
- [ ] Lambda Function URL 可正常存取（HTTPS）
- [ ] Lambda 冷啟動時間 < 5 秒（可接受）
- [ ] DynamoDB 三張資料表均已建立，GSI 設定正確

---

## Phase 2：本機排程整合

### 功能正確性
- [ ] 排程腳本依 UTC 時間正確篩選到期訂閱
- [ ] yt-dlp 成功下載指定頻道最新 Shorts（≤ 60 秒）
- [ ] Whisper 轉錄結果語言標註為 "en" 才繼續寄送
- [ ] 非英文影片在 history 表記錄 status=skipped_language
- [ ] Gmail 成功寄送（含文字稿內文與音訊附件）
- [ ] 成功寄送後 history 表記錄 status=done
- [ ] 寄送失敗時 history 表記錄 status=failed（不影響其他訂閱）

### 程式品質
- [ ] 錯誤處理完整（try/except，失敗不中斷其他訂閱處理）
- [ ] 日誌記錄完整（logs/ 目錄，含時間戳記）
- [ ] 所有函式具備繁體中文函式級註解

### 安全性
- [ ] IAM User 憑證存放於本機 AWS credentials 檔案（非程式碼）
- [ ] IAM Policy 限定只能存取指定的三張 DynamoDB 表
- [ ] Gmail OAuth token 不提交至版本控制

### 部署鏈路
- [ ] Windows 工作排程器每分鐘正確觸發腳本
- [ ] 腳本執行不需要人工干預（全自動化）
- [ ] 電腦重開機後工作排程器自動恢復

---

## Phase 3：前端（React）

### 功能正確性
- [ ] 登入成功後 JWT 存入 localStorage，頁面跳轉至訂閱列表
- [ ] 未登入時存取受保護頁面，自動導向 /login
- [ ] 登出後 JWT 清除，無法再存取受保護頁面
- [ ] 訂閱列表正確顯示所有訂閱及最後寄送狀態
- [ ] 新增訂閱時可呼叫後端驗證頻道 URL 是否有效
- [ ] 發送時間在前端以本地時間顯示，送出前換算為 UTC
- [ ] 已達 5 個訂閱時，新增訂閱按鈕停用或顯示提示
- [ ] 歷史紀錄依寄送時間降冪排序顯示

### 程式品質
- [ ] TypeScript 嚴格模式，無型別錯誤
- [ ] 所有函式具備繁體中文函式級註解
- [ ] axios 攔截器自動附加 JWT（不需每次手動傳入）
- [ ] API 錯誤有適當的 UI 提示（錯誤訊息顯示給用戶）

### 安全性
- [ ] JWT 存放於 localStorage（原型可接受，正式版考慮 httpOnly cookie）
- [ ] API base URL 透過環境變數設定（不硬編碼）
- [ ] 不在前端暴露任何 AWS 憑證

### 部署鏈路
- [ ] `npm run dev` 本地開發正常
- [ ] `npm run build` 成功產生 dist/ 目錄
- [ ] build 後的靜態檔案可正常載入（無 console error）

---

## Phase 4：部署

### 功能正確性
- [ ] 透過 CloudFront 網址可正常存取前端
- [ ] SPA 路由（如直接存取 /subscriptions）不出現 403/404
- [ ] 前端透過 CloudFront 呼叫 Lambda Function URL 正常（CORS 無誤）
- [ ] 前端 API 請求使用 HTTPS

### 安全性
- [ ] S3 bucket 不開放公開存取（僅限 CloudFront OAC）
- [ ] CloudFront 使用 HTTPS（不允許 HTTP 重導向）
- [ ] Lambda Function URL CORS 限縮為 CloudFront 網域

### 部署鏈路
- [ ] `npm run build` + `cdk deploy YtToMailFrontendStack` 完成上傳與 CloudFront Invalidation（BucketDeployment 自動觸發）
- [ ] 部署後瀏覽器載入最新版本，無需手動執行 `aws cloudfront create-invalidation`

### 整體系統驗收
- [ ] 完整端到端測試：註冊 → 新增訂閱 → 本機排程執行 → 收到郵件 → 歷史紀錄顯示
- [ ] 系統在 ≤ 20 用戶規模下費用符合預期（~$1/月）

---

# yt-to-mail v3 驗收清單

**版本**：3.0
**最後更新**：2026-05-03

---

## Phase 5：公開訂閱 API + 前端公開頁

### 後端公開 API（step10）

#### 功能正確性
- [x] `POST /public/subscribe` 成功新增訂閱，response 含 `auto_cancel_days` 欄位
- [x] `POST /public/subscribe` 第 6 個訂閱（同 email）回傳 400
- [x] `POST /public/subscribe` 無效 channel_url 回傳 400
- [x] `POST /public/subscribe` 以 `recipient_email` 作為 `user_id` 儲存
- [x] `GET /public/subscriptions?email=xxx` 回傳正確訂閱清單
- [x] `GET /public/subscriptions?email=xxx` 含 `no_new_video_days` 欄位（預設 0）
- [x] `DELETE /public/subscriptions/{id}?email=xxx` 正確刪除訂閱
- [x] `DELETE /public/subscriptions/{id}?email=wrong` 回傳 403
- [x] 所有 /public/* 端點無需 Authorization header

#### 相容性
- [x] 現有私有 API（GET/POST/PUT/DELETE /subscriptions）不受影響
- [x] `SubscriptionResponse` 新增 `auto_cancel_days`（預設 3）、`no_new_video_days`（預設 0）向後相容

### 前端公開訂閱頁（step12）

- [x] 直接存取 `/`（未登入）顯示訂閱表單，不跳轉登入
- [x] 表單含 `recipient_email`、`channel_url`、`audio_speed`、`send_time`、`auto_cancel_days`
- [x] `auto_cancel_days` 預設 3，min=1 驗證正常（輸入 0 顯示錯誤）
- [x] 步驟 1 呼叫 `POST /channels/verify` 顯示頻道名稱
- [x] 步驟 2 呼叫 `POST /public/subscribe`（非需要 JWT 的私有 API）
- [x] `send_time` 顯示本地時間，送出前換算 UTC
- [x] 成功後顯示成功訊息（不跳轉），含「查看我的訂閱」連結

### 前端 Email 查詢頁（step13）

- [x] 直接存取 `/my-subscriptions`（未登入）顯示查詢頁，不跳轉登入
- [x] 輸入有效 email 查詢，顯示正確訂閱清單
- [x] 每筆訂閱顯示：頻道名稱、發送時間（本地）、語速、建立時間
- [x] `no_new_video_days = 0` 顯示「尚無無新影片記錄」
- [x] `no_new_video_days > 0` 顯示「連續無新影片：N 天 / 設定上限：M 天」
- [x] 取消訂閱確認後呼叫 `DELETE /public/subscriptions/{id}?email={email}`
- [x] 取消成功後訂閱從清單消失

---

## Phase 6：管理員後台

### 後端管理員 API（step11）

#### 功能正確性
- [x] `POST /auth/login` 以 admin email + 正確密碼登入，JWT 含 `is_admin: true`
- [x] `POST /auth/login` 以一般 email 登入，JWT 不含 `is_admin`
- [x] `GET /admin/subscriptions` 以 admin JWT 取得全表資料
- [x] `GET /admin/subscriptions?email=xxx` 只回傳該 email 的訂閱
- [x] `GET /admin/subscriptions` 以一般用戶 JWT 回傳 403
- [x] `DELETE /admin/subscriptions/{id}` 以 admin JWT 可刪除任意訂閱

#### CDK / 基礎設施
- [x] CDK BackendStack 含 `ADMIN_EMAIL`、`ADMIN_PASSWORD_HASH` 環境變數
- [x] `cdk synth` 通過，`tsc --noEmit` 無錯誤
- [x] `ADMIN_EMAIL` 為空時 login 端點正常處理一般用戶（不崩潰）

### 前端管理員後台（step14）

- [x] 直接存取 `/admin/subscriptions`（無 admin token）重導至 `/admin/login`
- [x] 以正確 admin 帳密登入後跳轉至 `/admin/subscriptions`
- [x] 頁面載入顯示全表訂閱資料
- [x] Email 篩選正確呼叫 `GET /admin/subscriptions?email=xxx`
- [x] 每筆訂閱顯示：用戶 email、頻道名稱、發送時間（UTC）、語速、無新影片計數
- [x] 「取消訂閱」確認後刪除，從列表消失
- [x] 登出後清除 admin token，重導至 `/admin/login`

---

## Phase 7：排程器自動取消

### 排程器自動取消計數器（step15）

#### 功能正確性
- [x] `status=done` 時 DynamoDB 中 `no_new_video_days` 更新為 0
- [x] `status=skipped_duplicate` 時 `no_new_video_days` 加 1
- [x] `no_new_video_days >= auto_cancel_days` 時觸發自動取消（刪除訂閱、寄通知信）
- [x] 未達上限時回傳 `skipped_duplicate`，訂閱不被刪除
- [x] 自動取消通知信含頻道名稱、天數、重新訂閱連結
- [x] 舊有訂閱（無 `auto_cancel_days` 欄位）以預設值 3 運作，不崩潰

#### 安全性
- [x] `increment_no_new_video_days` 使用 DynamoDB 原子 ADD 操作（非 read-then-write）
- [x] IAM Policy 更新：排程器 user 具備 `dynamodb:UpdateItem`、`dynamodb:DeleteItem` 於 subscriptions 表

#### 程式品質
- [x] `cdk synth` 通過（IAM Policy 更新）
- [x] 所有新增函式具備繁體中文函式級註解
- [x] Python type hints 正確標注，無 `any` 型別

---

# yt-to-mail v4 驗收清單

**版本**：4.0
**最後更新**：2026-05-03

---

## Phase 8：Shorts 篩選功能

### URL 解析與存儲（step16 — channels.py、public.py）

- [ ] 輸入 `https://www.youtube.com/@melrobbins/shorts`，`POST /channels/verify` 回應 `channel_url` 為 `https://www.youtube.com/@melrobbins/shorts`
- [ ] 輸入 `https://www.youtube.com/@melrobbins/shorts/`（尾部斜線），正規化輸出不含雙斜線，結果同上
- [ ] 輸入 `https://www.youtube.com/@melrobbins`，`POST /channels/verify` 回應 `channel_url` 為 `https://www.youtube.com/@melrobbins`（不含 `/shorts`）
- [ ] 輸入 `https://www.youtube.com/@melrobbins/videos`，正規化輸出為 `https://www.youtube.com/@melrobbins`（不含後綴）
- [ ] `POST /public/subscribe` 傳入含 `/shorts` 的 URL，DynamoDB 存入 `channel_url` 保留 `/shorts`
- [ ] `POST /public/subscribe` 傳入不含 `/shorts` 的 URL，DynamoDB 存入 `channel_url` 不含 `/shorts`
- [ ] 前端 `defaultValues.channel_url = "https://www.youtube.com/@melrobbins/shorts"` 通過 `POST /channels/verify` 後，回傳 `channel_url` 保留 `/shorts`

### 排程器播放清單選擇（step16 — processor.py）

- [ ] `channel_url` 以 `/shorts` 結尾時，yt-dlp 查詢 URL 直接使用 `channel_url`（不 append `/videos`）
- [ ] `channel_url` 不含 `/shorts` 時，yt-dlp 查詢 URL 為 `channel_url + "/videos"`（維持現有行為）
- [ ] 舊有 `/channel/UCxxx` 格式訂閱，yt-dlp 查詢 URL 為 `/channel/UCxxx/videos`（行為不變）

### 向下相容性

- [ ] 現有無 `/shorts` 的訂閱，排程器行為與 step16 前完全一致
- [ ] 不需要 DynamoDB backfill，舊資料正常運作

### 程式品質

- [ ] `tsc --noEmit` 通過（無 CDK TypeScript 修改，既有 Stack 未受影響）
- [ ] 所有修改函式具備繁體中文函式級註解
