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
