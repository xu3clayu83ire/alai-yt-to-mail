"""語音轉文字模組測試：mock imageio_ffmpeg 與 Whisper，不需要實際模型或音訊檔。"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from src.transcriber import transcribe, TranscriptResult, TranscriptionError


@pytest.fixture
def audio_file(tmp_path):
    """建立假的音訊檔案供測試使用。"""
    p = tmp_path / "test.m4a"
    p.write_bytes(b"fake audio content")
    return str(p)


def test_transcribe_returns_result(audio_file):
    """成功轉錄時應回傳 TranscriptResult。"""
    fake_audio = np.zeros(16000, dtype=np.float32)
    mock_result = {
        "text": "  這是測試文字稿  ",
        "language": "zh",
        "segments": [{"end": 30.5}],
    }

    with patch("src.transcriber._load_audio_numpy", return_value=fake_audio):
        with patch("src.transcriber._get_model") as mock_get_model:
            mock_get_model.return_value.transcribe.return_value = mock_result
            result = transcribe(audio_file)

    assert isinstance(result, TranscriptResult)
    assert result.text == "這是測試文字稿"
    assert result.language == "zh"
    assert result.duration_seconds == 30.5


def test_transcribe_file_not_found():
    """音訊檔不存在時應立即拋出 TranscriptionError。"""
    with pytest.raises(TranscriptionError, match="音訊檔不存在"):
        transcribe("/nonexistent/path.m4a")


def test_transcribe_ffmpeg_failure(audio_file):
    """ffmpeg 解碼失敗時應拋出 TranscriptionError。"""
    with patch("src.transcriber._load_audio_numpy", side_effect=TranscriptionError("音訊解碼失敗")):
        with pytest.raises(TranscriptionError, match="音訊解碼失敗"):
            transcribe(audio_file)
