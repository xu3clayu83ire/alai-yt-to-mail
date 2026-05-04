/**
 * 訂閱列表頁面（首頁）
 * 顯示所有訂閱，提供啟用/停用切換與刪除功能
 * 使用 TanStack Query 管理 API 快取，確保資料操作後自動更新
 */

import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSubscriptions, updateSubscription, deleteSubscription } from '../api/subscriptions';
import { SubscriptionCard } from '../components/SubscriptionCard';

const MAX_SUBSCRIPTIONS = 5;

/**
 * 訂閱列表頁面元件
 * 啟用切換與刪除操作成功後自動 invalidate query 觸發重新載入
 */
export function SubscriptionListPage() {
  const queryClient = useQueryClient();

  /** 取得訂閱列表 */
  const { data: subscriptions = [], isLoading, error } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: getSubscriptions,
  });

  /** 更新訂閱（啟用/停用）*/
  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      updateSubscription(id, { is_active: isActive }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });

  /** 刪除訂閱 */
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSubscription(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });

  /**
   * 處理啟用/停用切換
   */
  const handleToggleActive = (id: string, isActive: boolean) => {
    toggleMutation.mutate({ id, isActive });
  };

  /**
   * 處理刪除訂閱，呼叫前以 window.confirm 要求用戶確認
   */
  const handleDelete = (id: string, channelName: string) => {
    if (window.confirm(`確定要刪除「${channelName}」的訂閱嗎？此操作無法還原。`)) {
      deleteMutation.mutate(id);
    }
  };

  const subscriptionCount = subscriptions.length;
  const isAtLimit = subscriptionCount >= MAX_SUBSCRIPTIONS;

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <p className="text-gray-500">載入中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-red-600">載入訂閱失敗，請重新整理頁面</p>
      </div>
    );
  }

  return (
    <div>
      {/* 頁面標題列 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          我的訂閱（{subscriptionCount}/{MAX_SUBSCRIPTIONS}）
        </h2>
        <Link
          to="/subscriptions/add"
          className={`text-sm font-medium px-4 py-2 rounded-md transition-colors ${
            isAtLimit
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed pointer-events-none'
              : 'bg-red-600 text-white hover:bg-red-700'
          }`}
          aria-disabled={isAtLimit}
        >
          新增訂閱
        </Link>
      </div>

      {/* 訂閱列表 */}
      {subscriptions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">尚無訂閱</p>
          <Link
            to="/subscriptions/add"
            className="inline-block bg-red-600 text-white px-6 py-2 rounded-md font-medium hover:bg-red-700 transition-colors"
          >
            立即新增
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2">
          {subscriptions.map((subscription) => (
            <SubscriptionCard
              key={subscription.id}
              subscription={subscription}
              onToggleActive={handleToggleActive}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* 管理後台連結 */}
      <div className="mt-8 text-center">
        <Link to="/admin/login" className="text-xs text-gray-400 hover:text-gray-600 transition-colors">
          管理後台
        </Link>
      </div>
    </div>
  );
}
