# CORS 重複 header 導致 net::ERR_FAILED — FastAPI CORSMiddleware 與 Lambda Function URL 衝突

**日期**：2026-05-02  
**類型**：問題排除  
**適用專案**：yt-to-mail（`d:\12_Claude_Assistant\yt-to-mail`）

---

## 發生了什麼

前端從 CloudFront (`https://drtl6k13ydgdp.cloudfront.net`) 呼叫 Lambda Function URL，POST `/auth/register` 伺服器回傳 201 Created，但瀏覽器顯示 `net::ERR_FAILED 201 (Created)`，前端顯示「註冊失敗」。

瀏覽器 console 錯誤訊息：

```
POST https://3ebypr4fzncraswkfl5xyk5u4m0pegfh.lambda-url.us-east-1.on.aws/auth/register net::ERR_FAILED 201 (Created)
```

伺服器端已成功處理請求（HTTP 201），但 axios 讀不到 response，拋出 network error，前端誤判為失敗。

## 根本原因

Response Headers 出現兩個 `access-control-allow-origin`：

```
access-control-allow-origin: *                                     ← FastAPI CORSMiddleware 加的
access-control-allow-origin: https://drtl6k13ydgdp.cloudfront.net ← Lambda Function URL 加的
```

Chrome（及所有現代瀏覽器）遇到重複的 `access-control-allow-origin` header 時，會依照 CORS 規範直接拒絕整個回應——即使伺服器已成功處理請求、HTTP status 也正常。axios 在這種情況下無法讀到 response body，拋出 network error。

兩層 CORS 設定同時存在的原因：

- `main.py` 的 `CORSMiddleware` 設定 `allow_origins=["*"]`，每個 response 都會附加 `access-control-allow-origin: *`
- Lambda Function URL 的 CORS 設定（在 CDK 或 AWS Console 中啟用）也會對符合 allowlist 的 origin 自動附加 `access-control-allow-origin: https://drtl6k13ydgdp.cloudfront.net`
- 兩層互不知曉對方的存在，每層都盡責地加上 header，結果兩個值同時出現

## 解法

移除 FastAPI `main.py` 中的 `CORSMiddleware`，由 Lambda Function URL 統一處理 CORS：

```python
# 移除這段
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)

# 改為註解說明
# CORS 由 Lambda Function URL 統一處理，不在應用層重複設定，
# 避免 access-control-allow-origin 重複出現導致瀏覽器拒絕回應。
```

Lambda Function URL 端維持原本的 CORS 設定，允許 `https://drtl6k13ydgdp.cloudfront.net`。

## 風險與注意事項

**唯一原則：CORS 只能由一層處理，二選一。**

| 選擇 | 保留 | 移除 |
|------|------|------|
| 由 Lambda Function URL 處理 | Lambda Function URL 的 CORS 設定 | FastAPI `CORSMiddleware` |
| 由 FastAPI 處理 | FastAPI `CORSMiddleware` | Lambda Function URL 的 CORS 設定（`cors` 屬性設為 none） |

注意事項：

- 本次選擇由 Lambda Function URL 處理。若未來改用 ALB 或 API Gateway 作為入口，需重新評估 CORS 由哪一層負責。
- Lambda Function URL CORS 設定若改動（例如新增允許的 origin），需重新部署 CDK stack，不能只重新部署 Lambda 函式碼。
- 本地端開發（直接跑 uvicorn）不經過 Lambda Function URL，若需本地測試跨域，需暫時加回 `CORSMiddleware` 或使用其他方式（如 browser extension 暫時關閉 CORS 檢查）。
- Chrome 對重複 CORS header 的拒絕行為是規範要求，其他瀏覽器（Firefox、Safari）行為相同，不是 Chrome 特有問題。

## 參考資料

- [Fetch 規範 — CORS 檢查](https://fetch.spec.whatwg.org/#cors-check)：規範中明確說明 `Access-Control-Allow-Origin` 若有多個值或格式不合法，視為 CORS 失敗
- [AWS Lambda Function URL CORS 設定文件](https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html#urls-cors)
- [FastAPI CORSMiddleware 文件](https://fastapi.tiangolo.com/tutorial/cors/)
