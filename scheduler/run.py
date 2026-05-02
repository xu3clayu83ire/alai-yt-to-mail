"""
run.py — 排程器主入口

Windows 工作排程器每分鐘呼叫此腳本。
執行流程：
1. 設定日誌（TimedRotatingFileHandler，每日 rotate，保留 7 天）
2. 查詢當前 UTC 分鐘到期的訂閱清單
3. 對每個訂閱呼叫 processor.process_subscription()
4. 個別 try/except 確保單一訂閱失敗不中斷其他訂閱
5. 記錄整體執行統計與耗時

設計原則：此腳本只負責流程協調與日誌，核心邏輯分散在各模組中。
Windows 工作排程器的 MultipleInstances=IgnoreNew 確保不會重疊執行，
但此腳本本身不實作鎖定機制。
"""

import logging
import logging.handlers
import os
import sys
import time

# 將 scheduler/ 目錄加入 Python 路徑，確保模組可被正確 import
_scheduler_dir = os.path.dirname(os.path.abspath(__file__))
if _scheduler_dir not in sys.path:
    sys.path.insert(0, _scheduler_dir)

import dynamo_reader
import processor


def _setup_logging() -> logging.Logger:
    """
    設定排程器日誌系統。
    使用 TimedRotatingFileHandler 每日 rotate 一次，保留最近 7 天的日誌，
    方便排查問題同時避免日誌檔案無限增長。
    日誌同時輸出到檔案與 stdout，方便在 Windows 工作排程器中查看即時狀態。
    日誌目錄自動建立，不需手動建立 logs/ 資料夾。
    """
    logs_dir = os.path.join(_scheduler_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "scheduler.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 日誌格式：包含時間（UTC）、等級、模組名稱與訊息
    formatter = logging.Formatter(
        fmt="[%(asctime)s UTC] %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 每日 rotate，保留 7 天（backupCount=7）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
        utc=True,  # 使用 UTC 時間觸發 rotate，與業務邏輯時間一致
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 同時輸出到 stdout（方便 Windows 工作排程器的執行記錄查看）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logging.getLogger(__name__)


def main() -> None:
    """
    排程器主執行函式。
    每次被 Windows 工作排程器呼叫時執行一輪完整流程：
    查詢到期訂閱 → 逐一處理 → 記錄統計結果。
    個別訂閱處理失敗不中斷後續訂閱的執行（個別 try/except 包裝）。
    整體執行時間記錄在日誌中，方便監控是否超出 5 分鐘的工作排程器時限。
    """
    logger = _setup_logging()
    start_time = time.time()
    current_utc = dynamo_reader.get_current_utc_hhmm()

    logger.info(f"開始執行，當前 UTC 時間：{current_utc}")

    # 查詢當前分鐘到期的訂閱清單
    try:
        subscriptions = dynamo_reader.get_due_subscriptions()
    except Exception as e:
        logger.error(f"查詢訂閱失敗，終止本次執行：{e}", exc_info=True)
        sys.exit(1)

    total = len(subscriptions)
    logger.info(f"查詢到 {total} 個訂閱")

    if total == 0:
        elapsed = time.time() - start_time
        logger.info(f"無到期訂閱，執行完成，耗時 {elapsed:.1f} 秒")
        return

    # 統計計數器
    count_done = 0
    count_failed = 0
    count_skipped = 0
    count_no_video = 0

    # 逐一處理每個訂閱（個別 try/except，失敗不中斷其他）
    for sub in subscriptions:
        sub_id = sub.get("id", "unknown")
        channel_url = sub.get("channel_url", "")
        channel_name = sub.get("channel_name", channel_url)

        logger.info(f"[sub:{sub_id}] 處理中 - 頻道: {channel_name}")

        try:
            result = processor.process_subscription(sub)
            status = result.get("status", "unknown")
            video_id = result.get("video_id")
            video_title = result.get("video_title")
            detected_language = result.get("detected_language", "")

            if status == "done":
                count_done += 1
                logger.info(
                    f"[sub:{sub_id}] 完成 - video_id: {video_id}, "
                    f"video_title: {video_title}, status: done"
                )
            elif status == "skipped_language":
                count_skipped += 1
                logger.info(
                    f"[sub:{sub_id}] 跳過 - status: skipped_language "
                    f"(detected: {detected_language})"
                )
            elif status == "no_video":
                count_no_video += 1
                logger.info(f"[sub:{sub_id}] 跳過 - 無符合條件的短影音")
            elif status == "skipped_duplicate":
                count_skipped += 1
                logger.info(
                    f"[sub:{sub_id}] 跳過 - 影片已寄過，已寄送無新影片通知 "
                    f"(video_id: {video_id})"
                )
            else:
                count_failed += 1
                error_msg = result.get("error_message", "")
                logger.warning(
                    f"[sub:{sub_id}] 失敗 - video_id: {video_id}, "
                    f"error: {error_msg}"
                )

        except Exception as e:
            # 捕捉 processor 未預期的例外，確保不中斷其他訂閱
            count_failed += 1
            logger.error(
                f"[sub:{sub_id}] 未預期錯誤（已跳過）：{e}",
                exc_info=True,
            )

    elapsed = time.time() - start_time
    logger.info(
        f"執行完成，耗時 {elapsed:.1f} 秒 | "
        f"總計: {total} | 完成: {count_done} | "
        f"失敗: {count_failed} | 跳過(語言/重複): {count_skipped} | "
        f"無影片: {count_no_video}"
    )


if __name__ == "__main__":
    main()
