"""
FastAPI 應用程式主入口模組。

使用 Mangum 將 FastAPI 應用包裝成 AWS Lambda handler，
讓 Lambda Function URL 能夠接收 HTTP 請求並路由至各子路由。
所有路由前綴與 CORS 設定均在此集中管理。
"""

from dotenv import load_dotenv
load_dotenv()  # 本機開發時從 .env 載入環境變數，Lambda 上無 .env 檔案時自動跳過

from fastapi import FastAPI
from mangum import Mangum

from routers import auth, subscriptions, history, channels

# 建立 FastAPI 應用實例
# 設定標題與說明，方便 /docs 自動文件辨識
app = FastAPI(
    title="yt-to-mail API",
    description="YouTube 摘要信件服務的雲端後端 API，提供用戶認證、訂閱管理與歷史查詢。",
    version="2.0.0",
)

# CORS 由 Lambda Function URL 統一處理，不在應用層重複設定，
# 避免 access-control-allow-origin 重複出現導致瀏覽器拒絕回應。

# 掛載各功能路由
app.include_router(auth.router, prefix="/auth", tags=["認證"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["訂閱管理"])
app.include_router(history.router, prefix="/history", tags=["歷史紀錄"])
app.include_router(channels.router, prefix="/channels", tags=["頻道驗證"])


@app.get("/health", tags=["健康檢查"])
async def health_check() -> dict:
    """
    健康檢查端點。
    提供 Lambda 冷啟動後的快速回應確認服務存活，
    同時也方便監控系統定期探測。
    """
    return {"status": "ok", "service": "yt-to-mail-api"}


# 以 Mangum 包裝成 Lambda handler
# lifespan="off" 避免 Mangum 在每次請求都重複觸發 FastAPI lifespan 事件
handler = Mangum(app, lifespan="off")
