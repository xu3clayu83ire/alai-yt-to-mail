"""Gmail 寄信模組：使用 OAuth 2.0 自動寄出含文字稿與音訊附件的郵件。"""

import base64
import os
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from src.youtube import VideoInfo
from src.transcriber import TranscriptResult

_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
_MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25MB，Gmail 附件限制


def _get_gmail_service(credentials_path: str, token_path: str):
    """建立 Gmail API 服務，處理 token 過期自動 refresh 與首次授權流程。"""
    creds: Credentials | None = None

    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 本地首次授權（GitHub Actions 環境應預先注入 token）
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, _SCOPES)
            creds = flow.run_local_server(port=0)

        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _build_message(
    recipient: str,
    video: VideoInfo,
    transcript: TranscriptResult,
    audio_path: str,
) -> dict:
    """組裝 MIME 郵件，含 HTML 正文與音訊附件（若在大小限制內）。"""
    msg = MIMEMultipart()
    msg["To"] = recipient
    msg["Subject"] = f"[yt-to-mail] {video.title} — {date.today()}"

    html_body = f"""
<h2>📹 {video.title}</h2>
<p>🔗 <a href="https://youtube.com/watch?v={video.video_id}">觀看影片</a></p>
<p>🗣️ 語言：{transcript.language} ｜ ⏱️ 時長：{transcript.duration_seconds:.0f} 秒</p>
<hr>
<h3>文字稿</h3>
<pre style="white-space:pre-wrap;font-family:sans-serif">{transcript.text}</pre>
"""
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 附加音訊檔（若未超過 Gmail 限制）
    if Path(audio_path).exists():
        file_size = Path(audio_path).stat().st_size
        if file_size <= _MAX_ATTACHMENT_SIZE:
            with open(audio_path, "rb") as f:
                part = MIMEBase("audio", "mpeg")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{Path(audio_path).name}"',
            )
            msg.attach(part)
        else:
            note = MIMEText(
                f"⚠️ 音訊檔 ({file_size // 1024 // 1024}MB) 超過 25MB，未附加。",
                "plain",
                "utf-8",
            )
            msg.attach(note)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_email(
    credentials_path: str,
    token_path: str,
    recipient: str,
    video: VideoInfo,
    transcript: TranscriptResult,
    audio_path: str,
) -> None:
    """寄出含文字稿與音訊附件的 Gmail 郵件。"""
    service = _get_gmail_service(credentials_path, token_path)
    message = _build_message(recipient, video, transcript, audio_path)

    try:
        service.users().messages().send(userId="me", body=message).execute()
    except HttpError as e:
        raise RuntimeError(f"Gmail 寄信失敗：{e}") from e
