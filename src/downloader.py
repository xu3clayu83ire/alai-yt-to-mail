"""音訊下載模組：使用 yt-dlp 將 YouTube 影片轉為 mp3 音訊檔。"""

import os
from pathlib import Path
import yt_dlp  # type: ignore


class DownloadError(Exception):
    """音訊下載失敗時拋出。"""


def download_audio(video_id: str, output_dir: str) -> str:
    """下載指定影片的音訊並轉為 mp3，回傳完成後的檔案路徑。

    若下載或轉換失敗，拋出 DownloadError 以便上層決定是否標記失敗。
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(output_dir, f"{video_id}.mp3")

    # 若已存在（前次中斷後重試），跳過下載
    if os.path.exists(output_path):
        return output_path

    ydl_opts: dict = {
        "format": "best[ext=mp4]/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "outtmpl": os.path.join(output_dir, f"{video_id}.%(ext)s"),
        "quiet": False,
        "no_warnings": False,
    }

    # 若有 cookies 檔（雲端環境繞過 bot 偵測），加入 yt-dlp 設定
    cookies_path = os.getenv("YOUTUBE_COOKIES_PATH")
    if cookies_path and Path(cookies_path).exists():
        ydl_opts["cookiefile"] = cookies_path
        # ios client 不需要 PO Token，對 Shorts 支援最好
        ydl_opts["extractor_args"] = {"youtube": {"player_client": ["ios", "android"]}}
        print(f"   🍪 使用 cookies：{cookies_path}（{Path(cookies_path).stat().st_size} bytes）")
    else:
        print(f"   ⚠️  未找到 cookies 檔：{cookies_path}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(f"影片 {video_id} 下載失敗：{e}") from e

    if not os.path.exists(output_path):
        raise DownloadError(f"影片 {video_id} 下載後找不到輸出檔：{output_path}")

    return output_path
