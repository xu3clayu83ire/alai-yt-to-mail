/**
 * 管理員訂閱管理頁面
 * 顯示全表訂閱資料，支援 email 篩選與強制取消訂閱操作
 * 此頁面不使用 Layout.tsx，採用獨立的管理後台 UI 風格
 * 時間顯示維持 UTC 格式，方便管理員除錯，不做本地時區換算
 * 401/403 錯誤表示 admin JWT 過期，自動清除 token 並跳轉至登入頁
 */

import { useState, useEffect, useCallback } from 'react';
import type { ReactElement } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminListSubscriptions, adminDeleteSubscription } from '../api/admin';
import { removeAdminToken } from '../utils/storage';
import { utcTimeToLocal } from '../utils/timezone';
import type { AdminSubscriptionItem } from '../types';

/**
 * 管理員後台頁面狀態型別
 * deletingId 追蹤正在進行刪除操作的訂閱 ID，避免重複點擊
 */
interface AdminPageState {
  subscriptions: AdminSubscriptionItem[];
  isLoading: boolean;
  error: string | null;
  filterEmail: string;
  deletingId: string | null;
}

/**
 * 管理員訂閱管理頁面元件
 * 頁面載入時自動查詢全表，支援依 email 動態篩選
 */
export function AdminSubscriptionsPage(): ReactElement {
  const navigate = useNavigate();

  const [state, setState] = useState<AdminPageState>({
    subscriptions: [],
    isLoading: true,
    error: null,
    filterEmail: '',
    deletingId: null,
  });

  /**
   * 處理 API 認證錯誤
   * 收到 AUTH_EXPIRED 錯誤時清除 admin token 並跳轉至登入頁
   * 此函式避免在多個 catch 區塊重複撰寫相同的登出邏輯
   */
  const handleAuthExpired = useCallback(
    (error: unknown): void => {
      if (error instanceof Error && error.message === 'AUTH_EXPIRED') {
        removeAdminToken();
        navigate('/admin/login', { replace: true });
      }
    },
    [navigate]
  );

  /**
   * 載入訂閱列表
   * 可選傳入 email 參數進行篩選，空值表示查詢全表
   */
  const loadSubscriptions = useCallback(
    async (email?: string): Promise<void> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const data = await adminListSubscriptions(email);
        setState((prev) => ({ ...prev, subscriptions: data, isLoading: false }));
      } catch (error: unknown) {
        handleAuthExpired(error);
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: '載入失敗，請重新整理',
        }));
      }
    },
    [handleAuthExpired]
  );

  /** 頁面首次載入時查詢全表 */
  useEffect(() => {
    void loadSubscriptions();
  }, [loadSubscriptions]);

  /**
   * 處理 email 篩選查詢
   * 以目前 filterEmail 狀態值呼叫 API，空值表示查詢全表
   */
  const handleFilter = (): void => {
    void loadSubscriptions(state.filterEmail || undefined);
  };

  /**
   * 清空篩選並查詢全表
   * 同時重置 filterEmail 狀態，確保 UI 顯示與查詢條件一致
   */
  const handleClearFilter = (): void => {
    setState((prev) => ({ ...prev, filterEmail: '' }));
    void loadSubscriptions(undefined);
  };

  /**
   * 取消訂閱操作
   * 顯示確認提示後呼叫 DELETE API，成功後從列表移除該筆資料
   * 避免用戶誤操作，確認提示顯示頻道名稱與用戶 email
   */
  const handleDelete = async (item: AdminSubscriptionItem): Promise<void> => {
    const confirmed = window.confirm(
      `確定要取消訂閱「${item.channel_name}」（${item.user_id}）嗎？`
    );
    if (!confirmed) return;

    setState((prev) => ({ ...prev, deletingId: item.id }));
    try {
      await adminDeleteSubscription(item.id);
      setState((prev) => ({
        ...prev,
        subscriptions: prev.subscriptions.filter((s) => s.id !== item.id),
        deletingId: null,
      }));
    } catch (error: unknown) {
      setState((prev) => ({ ...prev, deletingId: null }));
      handleAuthExpired(error);
      if (!(error instanceof Error && error.message === 'AUTH_EXPIRED')) {
        alert('取消訂閱失敗，請重試');
      }
    }
  };

  /**
   * 管理員登出：清除 admin token 並跳轉至 /admin/login
   * 使用 replace 避免回上一頁繞過登入保護
   */
  const handleLogout = (): void => {
    removeAdminToken();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 頁首：標題 + 登出按鈕 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">訂閱管理後台</h1>
            <p className="text-gray-500 text-sm mt-0.5">DailyCast Admin</p>
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            登出
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* 篩選區 */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label
                htmlFor="filter-email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                依 Email 篩選
              </label>
              <input
                id="filter-email"
                type="email"
                value={state.filterEmail}
                onChange={(e) =>
                  setState((prev) => ({ ...prev, filterEmail: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleFilter();
                }}
                placeholder="user@example.com"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={handleFilter}
              disabled={state.isLoading}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              查詢
            </button>
            <button
              onClick={handleClearFilter}
              disabled={state.isLoading}
              className="border border-gray-300 text-gray-700 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              查詢全部
            </button>
          </div>
        </div>

        {/* 狀態訊息 */}
        {state.error && (
          <div className="bg-red-50 border border-red-200 rounded-md px-4 py-3 mb-4">
            <p className="text-red-600 text-sm">{state.error}</p>
          </div>
        )}

        {/* 資料表格 */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          {state.isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-gray-500 text-sm">載入中...</p>
            </div>
          ) : state.subscriptions.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-gray-500 text-sm">無訂閱資料</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">用戶 Email</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">頻道名稱</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">收件信箱</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">發送時間 (本地)</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">語速</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">無新影片天數</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">建立時間 (UTC)</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">狀態</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {state.subscriptions.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                      {/* 用戶 Email */}
                      <td className="px-4 py-3 text-gray-900 font-mono text-xs">
                        {item.user_id}
                      </td>
                      {/* 頻道名稱（可點擊連結） */}
                      <td className="px-4 py-3">
                        <a
                          href={item.channel_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {item.channel_name}
                        </a>
                      </td>
                      {/* 收件信箱 */}
                      <td className="px-4 py-3 text-gray-700 text-xs">{item.recipient_email}</td>
                      {/* 發送時間（轉換為本地時間顯示） */}
                      <td className="px-4 py-3 text-gray-700 font-mono text-xs">
                        {utcTimeToLocal(item.send_time)}
                      </td>
                      {/* 語速 */}
                      <td className="px-4 py-3 text-gray-700">{item.audio_speed}x</td>
                      {/* 無新影片天數 / 自動取消天數 */}
                      <td className="px-4 py-3 text-gray-700">
                        {item.no_new_video_days} / {item.auto_cancel_days}
                      </td>
                      {/* 建立時間（UTC 格式） */}
                      <td className="px-4 py-3 text-gray-700 text-xs font-mono">
                        {item.created_at}
                      </td>
                      {/* 狀態標籤 */}
                      <td className="px-4 py-3">
                        {item.is_active ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            啟用
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                            停用
                          </span>
                        )}
                      </td>
                      {/* 操作按鈕 */}
                      <td className="px-4 py-3">
                        <button
                          onClick={() => void handleDelete(item)}
                          disabled={state.deletingId === item.id}
                          className="bg-red-600 text-white text-xs px-3 py-1.5 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {state.deletingId === item.id ? '取消中...' : '取消訂閱'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 資料筆數摘要 */}
        {!state.isLoading && state.subscriptions.length > 0 && (
          <p className="text-gray-500 text-xs mt-3 text-right">
            共 {state.subscriptions.length} 筆訂閱
          </p>
        )}
      </main>
    </div>
  );
}
