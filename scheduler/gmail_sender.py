"""
gmail_sender.py — Gmail API 寄信模組

使用 Google OAuth2 憑證透過 Gmail API 寄送郵件。
支援純文字 + HTML 雙版本內文，並附加 mp3 音訊檔案。
OAuth2 token 在首次授權後快取，後續自動以 refresh token 更新，
不需每次手動重新授權。
"""

import base64
import logging
import mimetypes
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

# Gmail API 僅需寄信權限，使用最小 OAuth2 scope
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _get_gmail_service():  # type: ignore[return]  # googleapiclient Resource has no public type stub
    """
    建立並回傳已授權的 Gmail API service 物件。
    優先使用已快取的 token.json，若 token 過期則以 refresh token 自動更新，
    若 token 不存在（首次執行）則啟動 OAuth2 授權流程（需本機瀏覽器）。
    使用 InstalledAppFlow 是因為本機排程器無法作為 web server 接收 OAuth2 callback。
    """
    credentials_file = config.get_gmail_credentials_file()
    token_file = config.get_gmail_token_file()

    creds: Credentials | None = None

    # 嘗試從快取 token.json 載入憑證
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, GMAIL_SCOPES)

    # token 不存在或已過期時重新取得授權
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 使用 refresh token 自動更新，不需人工介入
            creds.refresh(Request())
        else:
            # 首次執行需啟動瀏覽器授權流程
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        # 更新快取的 token.json 以供下次使用
        with open(token_file, "w") as token_out:
            token_out.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_transcription_email(
    recipient_email: str,
    video_title: str,
    channel_name: str,
    video_id: str,
    whisper_text: str,
    mp3_file_path: str,
) -> None:
    """
    寄送 YouTube 短影音逐字稿郵件給訂閱者。
    郵件包含純文字與 HTML 雙版本內文，確保不同郵件客戶端都能正常顯示。
    附加處理後的 mp3 音訊檔案，讓收件人可在郵件中直接播放或下載。
    主旨格式 '[yt-to-mail] {video_title}' 方便收件人識別與過濾郵件。
    """
    sender = config.get_gmail_sender()
    subject = f"[yt-to-mail] {video_title}"
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # 純文字版本內文
    plain_body = (
        f"頻道：{channel_name}\n"
        f"影片：{video_title}\n"
        f"YouTube 連結：{youtube_url}\n\n"
        f"文字稿：\n{whisper_text}"
    )

    # HTML 版本內文（使用超連結方便點擊）
    html_body = f"""
<html>
  <body>
    <p><strong>頻道：</strong>{channel_name}</p>
    <p><strong>影片：</strong>{video_title}</p>
    <p><strong>YouTube 連結：</strong><a href="{youtube_url}">{youtube_url}</a></p>
    <hr>
    <p><strong>文字稿：</strong></p>
    <p style="white-space: pre-wrap;">{whisper_text}</p>
  </body>
</html>
"""

    # 建立 MIME multipart 郵件（含文字與附件）
    message = MIMEMultipart("mixed")
    message["to"] = recipient_email
    message["from"] = sender
    message["subject"] = subject

    # 建立文字部分（純文字 + HTML 替代方案）
    text_part = MIMEMultipart("alternative")
    text_part.attach(MIMEText(plain_body, "plain", "utf-8"))
    text_part.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(text_part)

    # 附加 mp3 音訊檔案
    if os.path.exists(mp3_file_path):
        mime_type, _ = mimetypes.guess_type(mp3_file_path)
        if mime_type is None:
            mime_type = "audio/mpeg"
        main_type, sub_type = mime_type.split("/", 1)

        with open(mp3_file_path, "rb") as f:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(f.read())

        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(mp3_file_path),
        )
        message.attach(attachment)
    else:
        logger.warning(f"mp3 檔案不存在，跳過附件：{mp3_file_path}")

    # 使用 Gmail API 傳送郵件
    service = _get_gmail_service()
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()

    logger.info(f"郵件已寄出至 {recipient_email}，主旨：{subject}")


def send_no_new_video_email(
    recipient_email: str,
    channel_name: str,
    channel_url: str,
) -> None:
    """
    當頻道最新影片已寄過時，通知訂閱者目前無新影片可收聽。
    不附加音訊檔案，純文字通知即可。
    """
    sender = config.get_gmail_sender()
    subject = f"[yt-to-mail] {channel_name} 目前沒有新影片"

    plain_body = (
        f"頻道：{channel_name}\n"
        f"頻道連結：{channel_url}\n\n"
        f"此頻道的最新影片已在先前寄送過，目前尚無新影片可收聽。\n"
        f"等頻道發布新影片後，系統會自動寄送。"
    )

    html_body = f"""
<html>
  <body>
    <p><strong>頻道：</strong>{channel_name}</p>
    <p><strong>頻道連結：</strong><a href="{channel_url}">{channel_url}</a></p>
    <hr>
    <p>此頻道的最新影片已在先前寄送過，目前尚無新影片可收聽。</p>
    <p>等頻道發布新影片後，系統會自動寄送。</p>
  </body>
</html>
"""

    message = MIMEMultipart("alternative")
    message["to"] = recipient_email
    message["from"] = sender
    message["subject"] = subject
    message.attach(MIMEText(plain_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    service = _get_gmail_service()
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()

    logger.info(f"無新影片通知已寄出至 {recipient_email}，頻道：{channel_name}")
