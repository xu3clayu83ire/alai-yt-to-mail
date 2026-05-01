"""一次性 Gmail OAuth 授權腳本：執行後產生 token.json，供主程式與 GitHub Actions 使用。"""

from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import json
import os
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH", ".source/google_credentials_gmail.json")
token_path = os.getenv("GMAIL_TOKEN_PATH", ".source/gmail_token.json")

print(f"使用 credentials：{credentials_path}")
print("即將開啟瀏覽器，請登入你的 Google 帳號並點「允許」...")

flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
creds = flow.run_local_server(port=0)

Path(token_path).parent.mkdir(parents=True, exist_ok=True)
with open(token_path, "w") as f:
    f.write(creds.to_json())

print(f"\n✅ 授權完成！token 已儲存至：{token_path}")
print("\n請將以下內容複製，貼到 GitHub Secrets 的 GMAIL_TOKEN_JSON：")
print("-" * 60)
print(creds.to_json())
