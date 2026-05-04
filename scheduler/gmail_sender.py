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
    主旨格式 '[DailyCast] {video_title}' 方便收件人識別與過濾郵件。
    """
    sender = config.get_gmail_sender()
    subject = f"[DailyCast] {video_title}"
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
    subject = f"[DailyCast] {channel_name} 目前沒有新影片"

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


def send_auto_cancel_email(
    recipient_email: str,
    channel_name: str,
    auto_cancel_days: int,
    channel_url: str,
) -> None:
    """
    訂閱因連續 N 天無新影片達到 auto_cancel_days 上限時，寄送自動取消通知信。
    信中說明取消原因並附上重新訂閱連結，讓收件人可自行決定是否再次訂閱。
    重新訂閱連結來源為 config.get_frontend_url()，未設定時以提示文字替代，
    確保即使環境變數未設定也能正常寄出郵件。
    """
    sender = config.get_gmail_sender()
    subject = f"[DailyCast] 您對「{channel_name}」的訂閱已自動取消"

    frontend_url = config.get_frontend_url()
    if frontend_url:
        resubscribe_text = f"如需重新訂閱，請前往：{frontend_url}"
        resubscribe_html = f'如需重新訂閱，請前往：<a href="{frontend_url}">{frontend_url}</a>'
    else:
        resubscribe_text = "如需重新訂閱，請聯繫系統管理員取得訂閱頁面連結。"
        resubscribe_html = "如需重新訂閱，請聯繫系統管理員取得訂閱頁面連結。"

    plain_body = (
        f"頻道：{channel_name}\n"
        f"頻道連結：{channel_url}\n\n"
        f"由於此頻道已連續 {auto_cancel_days} 天未發布新影片，\n"
        f"您的訂閱已自動取消。\n\n"
        f"{resubscribe_text}"
    )

    html_body = f"""
<html>
  <body>
    <p><strong>頻道：</strong>{channel_name}</p>
    <p><strong>頻道連結：</strong><a href="{channel_url}">{channel_url}</a></p>
    <hr>
    <p>由於此頻道已連續 <strong>{auto_cancel_days} 天</strong>未發布新影片，您的訂閱已自動取消。</p>
    <p>{resubscribe_html}</p>
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

    logger.info(
        f"自動取消通知已寄出至 {recipient_email}，"
        f"頻道：{channel_name}，auto_cancel_days={auto_cancel_days}"
    )


def send_admin_removed_email(
    recipient_email: str,
    channel_name: str,
    channel_url: str,
) -> None:
    """
    管理員從白名單移除頻道時，通知受影響的訂閱者其訂閱已自動取消。

    此通知信不含重新訂閱連結，原因是頻道已從白名單移除，
    用戶無法再次訂閱同一頻道；信中說明移除原因讓收件人了解狀況，
    避免用戶以為是系統錯誤而重複聯絡客服。
    郵件結構與 send_auto_cancel_email 相同（MIMEMultipart alternative，純文字 + HTML），
    確保不同郵件客戶端都能正常顯示。
    """
    sender = config.get_gmail_sender()
    subject = f"[DailyCast] 您對「{channel_name}」的訂閱已由管理員移除"

    plain_body = (
        f"頻道：{channel_name}\n"
        f"頻道連結：{channel_url}\n\n"
        f"此頻道已由系統管理員從可訂閱清單中移除，\n"
        f"您的訂閱已自動取消。\n\n"
        f"如有疑問，請聯繫系統管理員。"
    )

    html_body = f"""
<html>
  <body>
    <p><strong>頻道：</strong>{channel_name}</p>
    <p><strong>頻道連結：</strong><a href="{channel_url}">{channel_url}</a></p>
    <hr>
    <p>此頻道已由系統管理員從可訂閱清單中移除，您的訂閱已自動取消。</p>
    <p>如有疑問，請聯繫系統管理員。</p>
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

    logger.info(f"管理員移除通知已寄出至 {recipient_email}，頻道：{channel_name}")
