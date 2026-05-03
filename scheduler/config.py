"""
config.py — 排程器設定讀取模組

從 .env 檔案讀取所有環境變數設定，集中管理本機排程器的設定值。
使用 python-dotenv 載入 .env，讓開發者不需手動設定系統環境變數，
也方便在不同環境（本機、測試）切換設定。
"""

import os
from dotenv import load_dotenv

# 載入 .env 檔案（位於 scheduler/ 目錄下）
load_dotenv()


def get_aws_region() -> str:
    """
    取得 AWS Region 設定。
    DynamoDB 資料表所在的 Region，用於建立 boto3 client。
    預設為 ap-northeast-1（東京）以配合原型階段部署位置。
    """
    return os.getenv("AWS_REGION", "ap-northeast-1")


def get_subscriptions_table() -> str:
    """
    取得 subscriptions DynamoDB 資料表名稱。
    排程器需要查詢此表以取得到期訂閱清單。
    """
    return os.getenv("SUBSCRIPTIONS_TABLE", "yt-to-mail-subscriptions")


def get_history_table() -> str:
    """
    取得 history DynamoDB 資料表名稱。
    排程器將每次處理結果（成功/失敗/略過）寫入此表。
    """
    return os.getenv("HISTORY_TABLE", "yt-to-mail-history")


def get_gmail_credentials_file() -> str:
    """
    取得 Gmail API credentials.json 的絕對路徑。
    此檔案由 Google Cloud Console 下載，包含 OAuth2 client 資訊。
    需使用絕對路徑，避免 Windows 工作排程器執行時工作目錄不一致的問題。
    """
    value = os.getenv("GMAIL_CREDENTIALS_FILE", "")
    if not value:
        raise ValueError("GMAIL_CREDENTIALS_FILE 環境變數未設定，請在 .env 中指定 credentials.json 的絕對路徑")
    return value


def get_gmail_token_file() -> str:
    """
    取得 Gmail API token.json 的絕對路徑。
    此檔案在首次 OAuth2 授權後自動產生，記錄 access/refresh token。
    需使用絕對路徑，與 credentials.json 同理。
    """
    value = os.getenv("GMAIL_TOKEN_FILE", "")
    if not value:
        raise ValueError("GMAIL_TOKEN_FILE 環境變數未設定，請在 .env 中指定 token.json 的絕對路徑")
    return value


def get_gmail_sender() -> str:
    """
    取得 Gmail 寄件人 Email 地址。
    必須與 OAuth2 授權帳號一致，否則 Gmail API 會拒絕寄信。
    """
    value = os.getenv("GMAIL_SENDER", "")
    if not value:
        raise ValueError("GMAIL_SENDER 環境變數未設定，請在 .env 中指定寄件人 Gmail 地址")
    return value


def get_whisper_model() -> str:
    """
    取得 Whisper 模型大小設定。
    可選值：tiny、base、small、medium、large。
    base 在速度與準確度之間取得平衡，適合原型階段的英文短影音轉錄。
    模型越大準確度越高，但需要更多記憶體與時間。
    """
    return os.getenv("WHISPER_MODEL", "base")


def get_ytdlp_output_dir() -> str:
    """
    取得 yt-dlp 暫存檔案目錄路徑。
    下載的音訊檔案在處理完成後會被清除，此目錄僅作為暫存用途。
    建議使用不在系統磁碟根目錄的路徑，避免暫存檔案積累佔用 C 槽空間。
    """
    return os.getenv("YTDLP_OUTPUT_DIR", "C:\\temp\\yt-to-mail")


def get_frontend_url() -> str:
    """
    取得前端公開訂閱頁 URL，用於自動取消通知信中的重新訂閱連結。
    若未設定 FRONTEND_URL 環境變數，回傳空字串，
    呼叫端（gmail_sender）負責處理空字串的顯示替代文字。
    """
    return os.environ.get("FRONTEND_URL", "")
