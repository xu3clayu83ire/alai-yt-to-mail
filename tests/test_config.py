"""設定模組測試：驗證缺少環境變數時會拋出正確錯誤。"""

import pytest
import importlib
import os


def test_missing_required_env_raises_error(monkeypatch):
    """缺少必要環境變數時，import config 應拋出 EnvironmentError。"""
    # 清除所有相關環境變數
    for key in ["YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_URL", "OPENAI_API_KEY",
                "GMAIL_CREDENTIALS_PATH", "RECIPIENT_EMAIL"]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(EnvironmentError, match="必要的環境變數"):
        import src.config
        # 強制重新載入以觸發模組頂層的 _require() 呼叫
        importlib.reload(src.config)


def test_optional_env_has_default(monkeypatch, tmp_path):
    """可選環境變數未設定時應使用預設值，不拋出錯誤。"""
    # 設定所有必要變數
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake_key")
    monkeypatch.setenv("YOUTUBE_CHANNEL_URL", "https://youtube.com/@test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", str(tmp_path / "creds.json"))
    monkeypatch.setenv("RECIPIENT_EMAIL", "test@example.com")
    # 不設定 DB_PATH，驗證預設值
    monkeypatch.delenv("DB_PATH", raising=False)

    import src.config
    importlib.reload(src.config)
    assert src.config.DB_PATH == "data/processed.db"
