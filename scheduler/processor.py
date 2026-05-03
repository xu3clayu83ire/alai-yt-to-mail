"""
processor.py — 核心排程處理流程模組

對每個到期訂閱執行完整的處理流程：
1. 使用 yt-dlp 查詢頻道最新 10 支影片，取最新一支
2. 下載最新影片的前 60 秒音訊（mp3 格式）
3. 若 audio_speed != 1.0，使用 FFmpeg atempo 調整播放速度
4. 使用 Whisper 進行語音轉文字
5. 判斷語言，非英文則記錄 skipped_language 並返回
6. 寄送 Gmail（含逐字稿與 mp3 附件）
7. 清除暫存音訊檔案
8. 回傳處理結果 dict

每個步驟失敗時都記錄詳細錯誤，暫存檔案無論成功或失敗都會被清除。
"""

import logging
import os
import subprocess
from typing import Any

import yt_dlp
import whisper

import config
import dynamo_updater
import gmail_sender
import history_writer

logger = logging.getLogger(__name__)

# 每次最多取用的音訊時長（秒）
MAX_AUDIO_SECONDS = 60

# 每次從頻道取回的候選影片數量（從最新到舊，找第一支未寄過的）
MAX_CANDIDATE_VIDEOS = 10

# audio_speed 的有效範圍（FFmpeg atempo 限制）
AUDIO_SPEED_MIN = 0.5
AUDIO_SPEED_MAX = 2.0

# Whisper 模型快取：每次執行只載入一次，避免重複讀取模型檔案造成的效能損耗
_whisper_model: whisper.Whisper | None = None


def _clamp_audio_speed(speed: float) -> float:
    """
    將 audio_speed 限制在 FFmpeg atempo 支援的有效範圍 [0.5, 2.0]。
    FFmpeg atempo filter 若收到超出範圍的值會發生錯誤，
    clamp 確保即使 DynamoDB 中的資料有誤也不會導致 FFmpeg 崩潰。
    """
    return max(AUDIO_SPEED_MIN, min(AUDIO_SPEED_MAX, speed))


_YOUTUBE_SECTION_SUFFIXES = ("/videos", "/shorts", "/streams", "/live", "/playlists", "/community")


def _build_channel_content_url(channel_url: str) -> str:
    """
    建立查詢影片清單的 URL。
    若 channel_url 已包含 /shorts、/videos 等 YouTube section 路徑，直接使用；
    否則附加 /videos，確保取得影片清單而非頻道首頁（避免 yt-dlp 回傳 channel ID）。
    """
    cleaned = channel_url.rstrip("/")
    for suffix in _YOUTUBE_SECTION_SUFFIXES:
        if cleaned.endswith(suffix):
            return cleaned
    return cleaned + "/videos"


def _get_recent_videos(channel_url: str) -> list[dict[str, Any]]:
    """
    使用 yt-dlp flat-playlist 模式查詢頻道最新 MAX_CANDIDATE_VIDEOS 支影片，回傳清單（從新到舊）。
    使用 flat-playlist 不實際下載影片，僅取得元資料，速度快且節省頻寬。
    若 channel_url 已包含 /shorts、/videos 等路徑，保留原始路徑確保查詢正確的影片分類；
    若為裸頻道 URL，附加 /videos 確保取得影片清單而非頻道首頁。
    過濾掉 ID 以 UC 開頭的條目（channel ID），確保清單中只有真實影片。
    若頻道無影片或取得失敗，回傳空 list 讓呼叫端決定如何處理。
    """
    videos_url = _build_channel_content_url(channel_url)

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "extract_flat": True,
        "playlist_items": f"1-{MAX_CANDIDATE_VIDEOS}",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(videos_url, download=False)

        if not info:
            logger.warning(f"無法取得頻道資訊：{channel_url}")
            return []

        entries = info.get("entries", []) or []
        # 防禦性過濾：YouTube channel ID 以 UC 開頭，非真實影片 ID
        valid = [e for e in entries if not e.get("id", "").startswith("UC")]

        logger.info(f"取得 {len(valid)} 支候選影片：{channel_url}")
        return valid

    except Exception as e:
        logger.error(f"查詢頻道影片失敗：{channel_url}, error={e}", exc_info=True)
        raise


def _download_audio(video_id: str, output_dir: str) -> str:
    """
    下載指定 video_id 的前 MAX_AUDIO_SECONDS 秒音訊並轉換為 mp3 格式。
    使用 download_ranges 限制只取前 60 秒，避免下載完整長影片。
    回傳下載後的 mp3 檔案絕對路徑。
    若下載失敗（網路問題、版權限制等），拋出例外供呼叫端處理。
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    mp3_path = os.path.join(output_dir, f"{video_id}.mp3")

    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "download_ranges": yt_dlp.utils.download_range_func(None, [(0, MAX_AUDIO_SECONDS)]),
        "force_keyframes_at_cuts": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"下載後 mp3 檔案不存在：{mp3_path}")

    logger.info(f"音訊下載完成（前 {MAX_AUDIO_SECONDS}s）：{mp3_path}")
    return mp3_path


def _adjust_audio_speed(input_path: str, output_dir: str, video_id: str, speed: float) -> str:
    """
    使用 FFmpeg atempo filter 調整音訊播放速度。
    speed 已經過 _clamp_audio_speed 限制在 [0.5, 2.0] 範圍內，
    確保 FFmpeg 不會因超出範圍的值而發生錯誤。
    回傳速度調整後的 mp3 檔案路徑。
    若 FFmpeg 執行失敗，拋出例外供呼叫端處理。
    """
    clamped_speed = _clamp_audio_speed(speed)
    output_path = os.path.join(output_dir, f"{video_id}_speed.mp3")

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-filter:a", f"atempo={clamped_speed}",
        "-y",  # 覆蓋輸出檔案
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg 速度調整失敗（code={result.returncode}）：{result.stderr}"
        )

    logger.info(f"音訊速度調整完成（{clamped_speed}x）：{output_path}")
    return output_path


def _get_whisper_model() -> whisper.Whisper:
    """
    取得（或初始化）Whisper 模型的單例實例。
    Whisper 模型檔案約 100MB–1.5GB，載入需數秒並佔用大量記憶體，
    因此在整個程序生命週期內只載入一次，供同一 run 中的所有訂閱共用。
    """
    global _whisper_model
    if _whisper_model is None:
        model_name = config.get_whisper_model()
        logger.info(f"首次載入 Whisper 模型：{model_name}")
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model


def _transcribe_audio(audio_path: str) -> tuple[str, str]:
    """
    使用 Whisper 對音訊檔案進行語音轉文字。
    fp16=False 是因為 CPU 推論不支援 fp16（半精度浮點數），
    強制使用 fp32 避免 CPU 上的數值錯誤。
    回傳 (language_code, transcription_text) tuple，
    language_code 為 Whisper 偵測到的語言（例如 'en'、'ja'、'zh'）。
    """
    model = _get_whisper_model()
    result = model.transcribe(audio_path, fp16=False)

    language: str = result.get("language", "unknown")
    text: str = result.get("text", "")

    logger.info(f"Whisper 轉錄完成，偵測語言：{language}")
    return language, text


def _cleanup_files(*file_paths: str) -> None:
    """
    清除指定的暫存音訊檔案。
    無論處理成功或失敗都應呼叫此函式，確保暫存目錄不會積累大量音訊檔案。
    忽略不存在的檔案，避免因檔案未建立（例如下載前就失敗）而拋出額外例外。
    """
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"已刪除暫存檔：{path}")
            except OSError as e:
                logger.warning(f"刪除暫存檔失敗（忽略）：{path}, error={e}")


def process_subscription(subscription: dict[str, Any]) -> dict[str, Any]:
    """
    對單一訂閱執行完整的排程處理流程。
    包含查詢影片、下載音訊、速度調整、Whisper 轉錄、語言判斷、Gmail 寄信、history 寫入。
    無論成功或失敗，暫存音訊檔案都會在最後清除。
    回傳包含 video_id、video_title、status、error_message 的結果 dict。
    若無符合條件的影片（無 ≤60s 短影音），回傳 status='no_video' 且不寫入 history。
    """
    subscription_id: str = subscription.get("id", "unknown")
    user_id: str = subscription.get("user_id", "unknown")
    channel_url: str = subscription.get("channel_url", "")
    recipient_email: str = subscription.get("recipient_email", "")
    audio_speed: float = float(subscription.get("audio_speed", 1.0))
    channel_name: str = subscription.get("channel_name", channel_url)

    output_dir = config.get_ytdlp_output_dir()

    # 使用明確的哨兵值追蹤已建立的暫存檔，確保 finally 可正確清理
    mp3_path: str = ""
    speed_mp3_path: str = ""
    # 在 try 外初始化，使 except 區塊可引用而不依賴 locals()
    video_id: str = "unknown"
    video_title: str = "unknown"

    try:
        # Step 1：查詢頻道最新 MAX_CANDIDATE_VIDEOS 支影片
        candidate_videos = _get_recent_videos(channel_url)
        if not candidate_videos:
            logger.info(f"[sub:{subscription_id}] 頻道無影片，跳過")
            return {
                "video_id": None,
                "video_title": None,
                "status": "no_video",
                "error_message": None,
            }

        # Step 2：找出第一支尚未寄過的影片（從最新到舊）
        # 以 user_id + channel_url 為範圍去重，避免同一用戶多個訂閱重複寄送相同影片
        sent_video_ids = history_writer.get_sent_video_ids(user_id, channel_url)
        video_info = next(
            (e for e in candidate_videos if e.get("id", "") not in sent_video_ids),
            None,
        )

        if video_info is None:
            logger.info(
                f"[sub:{subscription_id}] 近期 {len(candidate_videos)} 支影片均已寄過，"
                f"累加無新影片計數器"
            )
            auto_cancel_days: int = int(subscription.get("auto_cancel_days", 3))
            current_days = dynamo_updater.increment_no_new_video_days(subscription_id)

            if current_days >= 0 and current_days >= auto_cancel_days:
                # 連續無新影片天數達到上限，觸發自動取消流程
                logger.info(
                    f"[sub:{subscription_id}] 連續 {current_days} 天無新影片，"
                    f"達 auto_cancel_days={auto_cancel_days} 上限，觸發自動取消"
                )
                gmail_sender.send_auto_cancel_email(
                    recipient_email=recipient_email,
                    channel_name=channel_name,
                    auto_cancel_days=auto_cancel_days,
                    channel_url=channel_url,
                )
                dynamo_updater.delete_subscription(subscription_id)
                return {
                    "video_id": None,
                    "video_title": None,
                    "status": "auto_cancelled",
                    "error_message": None,
                }

            return {
                "video_id": None,
                "video_title": None,
                "status": "skipped_duplicate",
                "error_message": None,
            }

        video_id = video_info.get("id", "")
        video_title = video_info.get("title", video_id)
        logger.info(
            f"[sub:{subscription_id}] 找到未寄過的影片：{video_id} - "
            f"{video_title} ({video_info.get('duration', '?')}s)"
        )

        # Step 3：下載音訊為 mp3
        mp3_path = _download_audio(video_id, output_dir)

        # Step 4：若 audio_speed != 1.0，使用 FFmpeg 調整播放速度；
        # 調整後的檔案同時用於 Whisper 轉錄與郵件附件，保持語速一致
        if abs(audio_speed - 1.0) > 1e-6:
            speed_mp3_path = _adjust_audio_speed(mp3_path, output_dir, video_id, audio_speed)
            audio_file = speed_mp3_path
        else:
            audio_file = mp3_path

        # Step 4：Whisper 語音轉文字
        language, whisper_text = _transcribe_audio(audio_file)

        # Step 5：語言判斷，非英文則記錄 skipped_language 並返回
        if language != "en":
            logger.info(
                f"[sub:{subscription_id}] 偵測到非英文（{language}），"
                f"status=skipped_language"
            )
            history_writer.write_history(
                user_id=user_id,
                subscription_id=subscription_id,
                channel_url=channel_url,
                video_id=video_id,
                video_title=video_title,
                status="skipped_language",
            )
            return {
                "video_id": video_id,
                "video_title": video_title,
                "status": "skipped_language",
                "error_message": None,
                "detected_language": language,
            }

        # Step 6：Gmail 寄信（含逐字稿與 mp3 附件）
        gmail_sender.send_transcription_email(
            recipient_email=recipient_email,
            video_title=video_title,
            channel_name=channel_name,
            video_id=video_id,
            whisper_text=whisper_text,
            mp3_file_path=audio_file,
        )

        # Step 7：寫入 history（成功）
        history_writer.write_history(
            user_id=user_id,
            subscription_id=subscription_id,
            channel_url=channel_url,
            video_id=video_id,
            video_title=video_title,
            status="done",
        )

        # Step 7b：重置無新影片計數器
        # 頻道有新影片且寄信成功，清零 no_new_video_days 避免累積舊計數
        dynamo_updater.reset_no_new_video_days(subscription_id)

        logger.info(f"[sub:{subscription_id}] 處理完成 - video_id={video_id}, status=done")
        return {
            "video_id": video_id,
            "video_title": video_title,
            "status": "done",
            "error_message": None,
        }

    except Exception as e:
        error_message = str(e)
        logger.error(
            f"[sub:{subscription_id}] 處理失敗：{error_message}",
            exc_info=True,
        )

        # video_id / video_title 已在 try 外初始化，此處直接引用
        history_writer.write_history(
            user_id=user_id,
            subscription_id=subscription_id,
            channel_url=channel_url,
            video_id=video_id,
            video_title=video_title,
            status="failed",
            error_message=error_message,
        )

        return {
            "video_id": video_id,
            "video_title": video_title,
            "status": "failed",
            "error_message": error_message,
        }

    finally:
        # Step 8：無論成功或失敗，清除本次下載的暫存音訊檔案
        _cleanup_files(mp3_path, speed_mp3_path)
