"""語音轉文字模組：使用本地 Whisper 模型將音訊轉換為文字稿（完全免費）。"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np  # type: ignore
import imageio_ffmpeg  # type: ignore
import whisper  # type: ignore


@dataclass
class TranscriptResult:
    text: str
    language: str
    duration_seconds: float


class TranscriptionError(Exception):
    """語音轉文字失敗時拋出。"""


_MODEL_NAME = "base"
_model = None


def _get_model():
    """延遲載入模型，避免每次 import 都佔用記憶體。"""
    global _model
    if _model is None:
        print(f"   📦 載入 Whisper {_MODEL_NAME} 模型...")
        _model = whisper.load_model(_MODEL_NAME)
    return _model


def _load_audio_numpy(audio_path: str) -> np.ndarray:
    """用 imageio_ffmpeg 內建的 ffmpeg 將音訊解碼為 numpy array。

    直接傳給 Whisper，完全繞過 Whisper 內部的 ffmpeg 呼叫，不需要系統安裝 ffmpeg。
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg_exe, "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "f32le", "-loglevel", "quiet", "-"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise TranscriptionError(f"音訊解碼失敗：{result.stderr.decode(errors='ignore')}")
    return np.frombuffer(result.stdout, dtype=np.float32)


def transcribe(audio_path: str) -> TranscriptResult:
    """使用本地 Whisper 模型轉錄音訊，不需要 API Key，完全免費。"""
    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionError(f"音訊檔不存在：{audio_path}")

    try:
        audio = _load_audio_numpy(audio_path)
        model = _get_model()
        result = model.transcribe(audio, fp16=False)
        return TranscriptResult(
            text=result["text"].strip(),
            language=result.get("language", "unknown"),
            duration_seconds=result.get("segments", [{}])[-1].get("end", 0.0) if result.get("segments") else 0.0,
        )
    except TranscriptionError:
        raise
    except Exception as e:
        raise TranscriptionError(f"語音轉文字失敗：{e}") from e
