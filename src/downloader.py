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
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "outtmpl": os.path.join(output_dir, f"{video_id}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(f"影片 {video_id} 下載失敗：{e}") from e

    if not os.path.exists(output_path):
        raise DownloadError(f"影片 {video_id} 下載後找不到輸出檔：{output_path}")

    return output_path
