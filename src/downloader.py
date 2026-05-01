"""音訊下載模組：使用 yt-dlp 下載 YouTube 影片音訊（不需要 ffmpeg）。"""

import os
import glob
from pathlib import Path
import yt_dlp  # type: ignore


class DownloadError(Exception):
    """音訊下載失敗時拋出。"""


def download_audio(video_id: str, output_dir: str) -> str:
    """下載指定影片的音訊，回傳完成後的檔案路徑。

    直接下載原始格式（m4a 或 webm），不轉換，不需要 ffmpeg。
    回傳實際下載的檔案路徑（副檔名依 YouTube 提供的格式而定）。
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 若已有任何同 video_id 的音訊檔，直接回傳（避免重複下載）
    existing = glob.glob(os.path.join(output_dir, f"{video_id}.*"))
    if existing:
        return existing[0]

    ydl_opts: dict = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
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

    # 找到實際下載的檔案（副檔名不固定）
    downloaded = glob.glob(os.path.join(output_dir, f"{video_id}.*"))
    if not downloaded:
        raise DownloadError(f"影片 {video_id} 下載後找不到輸出檔")

    return downloaded[0]
