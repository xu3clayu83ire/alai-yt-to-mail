# JWT_SECRET_KEY 的作用與原理

**日期**：2026-05-02  
**類型**：技術決策 / 設定步驟

---

## 發生了什麼

在 yt-to-mail 專案中，`auth_service.py` 使用 `JWT_SECRET_KEY` 環境變數來簽發與驗證 JWT token，作為用戶身份認證的核心機制。

---

## 根本原因

JWT（JSON Web Token）依賴非對稱或對稱密鑰進行簽名，確保 token 內容無法被竄改。本專案使用 HMAC-SHA256（對稱）方式，只要持有相同的密鑰，任何一方都能驗證 token 的合法性。

---

## 解法

### 作用流程

```
登入成功
    │
    ▼
auth_service.py 用 JWT_SECRET_KEY 把 user_id 簽名成 token
    │
    ▼
回傳給前端（存在 localStorage）
    │
    ▼
前端每次 API 請求帶上 Authorization: Bearer <token>
    │
    ▼
auth_service.py 用同一把 JWT_SECRET_KEY 驗證 token 是否合法
    │
    ├── 合法 → 取出 user_id，繼續處理請求
    └── 不合法 → 回傳 401
```

### JWT token 結構

JWT token 分三段，以 `.` 串接：

```
eyJhbGciOiJIUzI1NiJ9         ← Header（演算法）
.eyJ1c2VyX2lkIjoiMTIzIn0     ← Payload（user_id 等資料，明文 Base64）
.SflKxwRJSMeKKF2QT4fwpMeJf   ← Signature（簽名）
```

**Payload 是明文**（Base64 編碼，非加密），任何人解碼後都能看到 user_id 等欄位，但無法偽造 Signature。

### 簽名原理

簽名的產生方式：

```
Signature = HMAC_SHA256(Header + "." + Payload, JWT_SECRET_KEY)
```

驗證時，伺服器重新計算：

```
重新算 = HMAC_SHA256(token 的 Header + "." + Payload, JWT_SECRET_KEY)

重新算 == token 的 Signature → 合法（這個 token 確實是我發的）
重新算 != token 的 Signature → 偽造（有人竄改過）
```

### 為什麼有效

就算有人把 Payload 裡的 `user_id` 改成別人的，Signature 就對不上——因為 Signature 是用原始 Payload 加上 JWT_SECRET_KEY 算出來的，改了 Payload 就無法重新算出相同的 Signature（沒有密鑰的情況下）。伺服器因此能拒絕偽造的 token。

---

## 風險與注意事項

- **不能放進 git**：`JWT_SECRET_KEY` 一旦洩漏，任何人可偽造任意用戶的 token，冒充任何人呼叫 API，不需要知道用戶密碼
- **Production 與開發環境應使用不同的 key**：若共用同一把 key，開發環境的 token 在 Production 也會被接受
- **key 長度建議**：至少 32 bytes 的隨機字串（可用 `python -c "import secrets; print(secrets.token_hex(32))"` 產生）
- **key 輪換困難**：更換 JWT_SECRET_KEY 後，所有已發出的 token 立即失效，所有在線用戶必須重新登入

### 在 yt-to-mail 的位置

| 環境 | 位置 |
|------|------|
| 本機開發 | `lambda/api/.env` 的 `JWT_SECRET_KEY` |
| Lambda 生產環境 | AWS Lambda Console → Configuration → Environment variables → 手動新增 `JWT_SECRET_KEY` |

---

## 參考資料

- [JWT 官方規格 RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
- [jwt.io — 線上解碼工具](https://jwt.io/)
- [HMAC-SHA256 說明](https://en.wikipedia.org/wiki/HMAC)
