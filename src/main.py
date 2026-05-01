"""主程式：整合所有模組，完整執行一次 YouTube → 下載 → 轉錄 → 寄信流程。"""

import os
import shutil
import tempfile
from pathlib import Path

from src import config
from src.database import init_db, is_processed, mark_processed
from src.youtube import get_channel_id, get_latest_shorts
from src.downloader import download_audio, DownloadError
from src.transcriber import transcribe, TranscriptionError
from src.mailer import send_email


def main() -> None:
    """主流程：每次執行處理當天未處理的 Shorts 影片。"""
    # 初始化資料庫（若尚不存在則建立）
    init_db(config.DB_PATH)
    print("✅ 資料庫初始化完成")

    # 取得頻道 ID
    channel_id = get_channel_id(config.YOUTUBE_API_KEY, config.YOUTUBE_CHANNEL_URL)
    print(f"✅ 頻道 ID：{channel_id}")

    # 取得最新 Shorts 清單
    videos = get_latest_shorts(config.YOUTUBE_API_KEY, channel_id)
    print(f"✅ 找到 {len(videos)} 部新影片")

    if not videos:
        print("ℹ️  今日沒有需要處理的影片，結束執行。")
        return

    # 暫存目錄（程式結束後清理）
    tmp_dir = tempfile.mkdtemp(prefix="yt-to-mail-")

    processed_count = 0
    failed_count = 0

    try:
        for video in videos:
            if is_processed(config.DB_PATH, video.video_id):
                print(f"⏭️  跳過已處理：{video.title}")
                continue

            print(f"▶️  處理：{video.title} ({video.video_id})")

            # 下載音訊
            try:
                audio_path = download_audio(video.video_id, tmp_dir)
                print(f"   ✅ 下載完成：{Path(audio_path).name}")
            except DownloadError as e:
                print(f"   ❌ 下載失敗：{e}")
                mark_processed(config.DB_PATH, video.video_id, video.title, channel_id, "failed")
                failed_count += 1
                continue

            # 語音轉文字
            try:
                transcript = transcribe(config.OPENAI_API_KEY, audio_path)
                print(f"   ✅ 轉錄完成（語言：{transcript.language}，{transcript.duration_seconds:.0f}秒）")
            except TranscriptionError as e:
                print(f"   ❌ 轉錄失敗：{e}")
                mark_processed(config.DB_PATH, video.video_id, video.title, channel_id, "failed")
                failed_count += 1
                continue

            # 寄送郵件
            try:
                send_email(
                    config.GMAIL_CREDENTIALS_PATH,
                    config.GMAIL_TOKEN_PATH,
                    config.RECIPIENT_EMAIL,
                    video,
                    transcript,
                    audio_path,
                )
                print(f"   ✅ 郵件已寄至 {config.RECIPIENT_EMAIL}")
            except RuntimeError as e:
                print(f"   ❌ 寄信失敗：{e}")
                mark_processed(config.DB_PATH, video.video_id, video.title, channel_id, "failed")
                failed_count += 1
                continue

            mark_processed(config.DB_PATH, video.video_id, video.title, channel_id, "done")
            processed_count += 1

    finally:
        # 清理暫存音訊檔
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n📊 執行摘要：成功 {processed_count} 部，失敗 {failed_count} 部")


if __name__ == "__main__":
    main()
