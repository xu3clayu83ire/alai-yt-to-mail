"""專案設定模組：從環境變數讀取所有設定，缺少必要值時立即報錯。"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 載入與 src/ 同層的 .env 檔（yt-to-mail/.env）
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)


def _require(key: str) -> str:
    """取得必要的環境變數，缺少時拋出明確錯誤而非使用預設值掩蓋問題。"""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"必要的環境變數 '{key}' 未設定。請複製 .env.example 為 .env 並填入正確的值。"
        )
    return value


# YouTube
YOUTUBE_API_KEY: str = _require("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_URL: str = _require("YOUTUBE_CHANNEL_URL")

# OpenAI Whisper
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")

# Gmail
GMAIL_CREDENTIALS_PATH: str = _require("GMAIL_CREDENTIALS_PATH")
GMAIL_TOKEN_PATH: str = os.getenv("GMAIL_TOKEN_PATH", ".source/gmail_token.json")

# 收件信箱
RECIPIENT_EMAIL: str = _require("RECIPIENT_EMAIL")

# SQLite
DB_PATH: str = os.getenv("DB_PATH", "data/processed.db")
