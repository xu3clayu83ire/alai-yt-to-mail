/**
 * 歷史紀錄頁面
 * 顯示所有寄送紀錄，支援「載入更多」分頁功能
 * 依 sent_at 降序顯示（後端排序），前端僅負責累加資料
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getHistory } from '../api/history';
import { HistoryItem } from '../components/HistoryItem';

const DEFAULT_LIMIT = 20;

/**
 * 歷史紀錄頁面元件
 * offset 累加實現「載入更多」，避免一次請求大量資料
 */
export function HistoryPage() {
  const [limit, setLimit] = useState(DEFAULT_LIMIT);

  const { data: historyItems = [], isLoading, error } = useQuery({
    queryKey: ['history', limit],
    queryFn: () => getHistory(limit, 0),
  });

  /**
   * 載入更多歷史紀錄
   * 增加 limit 值觸發 TanStack Query 重新請求更多資料
   */
  const handleLoadMore = () => {
    setLimit((prev) => prev + DEFAULT_LIMIT);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <p className="text-gray-500">載入中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-red-600">載入歷史紀錄失敗，請重新整理頁面</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">歷史紀錄</h2>

      {historyItems.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">尚無歷史紀錄</p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {historyItems.map((item) => (
              <HistoryItem key={item.id} item={item} />
            ))}
          </div>

          {/* 載入更多按鈕：當回傳筆數等於 limit 時顯示，表示可能還有更多資料 */}
          {historyItems.length >= limit && (
            <div className="text-center mt-6">
              <button
                onClick={handleLoadMore}
                className="bg-gray-100 text-gray-700 px-6 py-2 rounded-md font-medium hover:bg-gray-200 transition-colors"
              >
                載入更多
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
