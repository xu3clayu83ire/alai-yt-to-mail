/**
 * 歷史紀錄列表項目元件
 * 顯示單筆歷史紀錄，包含狀態標籤顏色與錯誤訊息 tooltip
 * sent_at 在此元件內從 UTC 轉換為本地時間顯示
 */

import type { HistoryItem as HistoryItemType } from '../types';
import { formatUtcTimestamp } from '../utils/timezone';

interface HistoryItemProps {
  item: HistoryItemType;
}

/** 各狀態對應的標籤樣式與文字 */
const statusConfig = {
  done: {
    label: '已寄出',
    className: 'bg-green-100 text-green-700',
  },
  failed: {
    label: '失敗',
    className: 'bg-red-100 text-red-700',
  },
  skipped_language: {
    label: '已跳過（非英文）',
    className: 'bg-gray-100 text-gray-600',
  },
} as const;

/**
 * 歷史紀錄項目顯示元件
 * 失敗狀態的標籤提供 title tooltip 顯示 error_message（若有）
 */
export function HistoryItem({ item }: HistoryItemProps) {
  const config = statusConfig[item.status];
  const youtubeUrl = `https://www.youtube.com/watch?v=${item.video_id}`;
  const localSentAt = formatUtcTimestamp(item.sent_at);

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4 flex items-start gap-4">
      {/* 狀態標籤 */}
      <div className="flex-shrink-0 mt-0.5">
        <span
          className={`inline-block px-2 py-1 rounded-md text-xs font-medium ${config.className}`}
          title={item.status === 'failed' && item.error_message ? item.error_message : undefined}
        >
          {config.label}
        </span>
      </div>

      {/* 影片資訊 */}
      <div className="flex-1 min-w-0">
        <a
          href={youtubeUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-gray-900 hover:text-blue-600 hover:underline block truncate"
        >
          {item.video_title}
        </a>
        <p className="text-xs text-gray-400 mt-1">{localSentAt}</p>
      </div>
    </div>
  );
}
