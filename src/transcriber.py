"""語音轉文字模組：使用 OpenAI Whisper API 將 mp3 轉換為文字稿。"""

import time
from dataclasses import dataclass
from pathlib import Path
from openai import OpenAI, APIError


@dataclass
class TranscriptResult:
    text: str
    language: str
    duration_seconds: float


class TranscriptionError(Exception):
    """語音轉文字失敗時拋出。"""


_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB，Whisper API 限制
_MAX_RETRIES = 3


def transcribe(api_key: str, audio_path: str) -> TranscriptResult:
    """呼叫 Whisper API 轉錄音訊，失敗時最多重試 3 次（指數退避）。

    超過 25MB 的音訊會警告並嘗試仍送出（由 API 端決定是否拒絕）。
    """
    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionError(f"音訊檔不存在：{audio_path}")

    file_size = path.stat().st_size
    if file_size > _MAX_FILE_SIZE_BYTES:
        print(f"⚠️  警告：音訊檔 {path.name} ({file_size // 1024 // 1024}MB) 超過 25MB 限制")

    client = OpenAI(api_key=api_key)

    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                )
            return TranscriptResult(
                text=response.text,
                language=getattr(response, "language", "unknown"),
                duration_seconds=getattr(response, "duration", 0.0),
            )
        except APIError as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                wait = 2 ** attempt  # 2s, 4s, 8s
                print(f"⚠️  Whisper API 第 {attempt} 次失敗，{wait} 秒後重試：{e}")
                time.sleep(wait)

    raise TranscriptionError(
        f"語音轉文字失敗（已重試 {_MAX_RETRIES} 次）：{last_error}"
    ) from last_error
