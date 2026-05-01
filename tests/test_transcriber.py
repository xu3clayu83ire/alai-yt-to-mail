"""語音轉文字模組測試：mock OpenAI API，驗證重試邏輯與錯誤處理。"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.transcriber import transcribe, TranscriptResult, TranscriptionError


@pytest.fixture
def audio_file(tmp_path):
    """建立假的音訊檔案供測試使用。"""
    p = tmp_path / "test.mp3"
    p.write_bytes(b"fake audio content")
    return str(p)


def test_transcribe_returns_result(audio_file):
    """成功轉錄時應回傳 TranscriptResult。"""
    mock_response = MagicMock()
    mock_response.text = "這是測試文字稿"
    mock_response.language = "zh"
    mock_response.duration = 30.5

    with patch("src.transcriber.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = mock_response

        result = transcribe("fake_key", audio_file)

    assert isinstance(result, TranscriptResult)
    assert result.text == "這是測試文字稿"
    assert result.language == "zh"
    assert result.duration_seconds == 30.5


def test_transcribe_file_not_found():
    """音訊檔不存在時應立即拋出 TranscriptionError，不呼叫 API。"""
    with pytest.raises(TranscriptionError, match="音訊檔不存在"):
        transcribe("fake_key", "/nonexistent/path.mp3")


def test_transcribe_retries_on_api_error(audio_file):
    """API 失敗時應重試，最終仍失敗則拋出 TranscriptionError。"""
    from openai import APIError

    with patch("src.transcriber.OpenAI") as mock_openai_cls:
        with patch("src.transcriber.time.sleep"):  # 跳過 sleep 加速測試
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            # 模擬 APIError — 需要 request 參數
            mock_request = MagicMock()
            mock_client.audio.transcriptions.create.side_effect = APIError(
                message="服務不可用", request=mock_request, body=None
            )

            with pytest.raises(TranscriptionError, match="已重試"):
                transcribe("fake_key", audio_file)

        # 確認重試了 3 次
        assert mock_client.audio.transcriptions.create.call_count == 3
