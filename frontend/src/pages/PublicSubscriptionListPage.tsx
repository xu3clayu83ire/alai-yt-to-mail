/**
 * 公開 Email 查詢頁面（/my-subscriptions）
 * 無需登入，讓用戶透過 email 查詢並管理自己的訂閱
 * 使用 React Hook Form + Zod 驗證，與其他頁面保持一致的開發模式
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { getPublicSubscriptions, deletePublicSubscription } from '../api/public';
import type { PublicSubscriptionItem } from '../types';
import { utcTimeToLocal, formatUtcTimestamp } from '../utils/timezone';

/** Email 查詢表單 schema */
const searchSchema = z.object({
  email: z.string().email('請輸入有效的 Email 格式'),
});

type SearchFormData = z.infer<typeof searchSchema>;

/** 頁面整體狀態 */
interface PageState {
  /** 目前查詢中的 email */
  email: string;
  /** 查詢結果（null 表示尚未查詢）*/
  subscriptions: PublicSubscriptionItem[] | null;
  /** 是否正在查詢中 */
  isLoading: boolean;
  /** 查詢錯誤訊息 */
  error: string | null;
  /** 正在刪除的訂閱 ID */
  deletingId: string | null;
  /** 刪除成功的訊息 */
  successMessage: string | null;
}

// ===================== 子元件 =====================

/**
 * 無新影片計數顯示元件
 * 依計數與上限決定顯示樣式：
 *   - noDays == 0：灰色文字「尚無無新影片記錄」
 *   - noDays > 0 且未接近上限：正常文字
 *   - noDays >= limit - 1：橘色警示，提醒用戶即將觸發自動取消
 */
function NoDaysCounter({ noDays, limit }: { noDays: number; limit: number }) {
  if (noDays === 0) {
    return <span className="text-gray-400 text-xs">尚無無新影片記錄</span>;
  }

  const isWarning = noDays >= limit - 1;

  return (
    <span className={`text-xs font-medium ${isWarning ? 'text-orange-600' : 'text-gray-600'}`}>
      {isWarning && (
        <span className="mr-1">⚠️</span>
      )}
      連續無新影片：{noDays} 天 / 設定上限：{limit} 天
    </span>
  );
}

/**
 * 單一訂閱卡片元件
 * 顯示頻道詳細資訊（名稱、發送時間、語速、建立時間、無新影片計數、狀態）
 * 並提供取消訂閱按鈕，點擊後觸發父元件的刪除流程
 */
interface PublicSubscriptionCardProps {
  subscription: PublicSubscriptionItem;
  onDelete: (id: string, channelName: string) => void;
  isDeleting: boolean;
}

function PublicSubscriptionCard({
  subscription,
  onDelete,
  isDeleting,
}: PublicSubscriptionCardProps) {
  const localSendTime = utcTimeToLocal(subscription.send_time);
  const formattedCreatedAt = formatUtcTimestamp(subscription.created_at);

  return (
    <div
      className="bg-white rounded-lg border p-5"
      style={{
        borderColor: '#efefef',
        boxShadow: '0 2px 12px rgba(0,0,0,0.05)',
      }}
    >
      {/* 頻道名稱與狀態標籤 */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm truncate">{subscription.channel_name}</h3>
          <a
            href={subscription.channel_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-500 hover:underline break-all"
          >
            {subscription.channel_url}
          </a>
        </div>
        <span
          className={`flex-shrink-0 text-xs font-medium px-2 py-1 rounded-full ${
            subscription.is_active
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-gray-100 text-gray-500 border border-gray-200'
          }`}
        >
          {subscription.is_active ? '啟用中' : '已停用'}
        </span>
      </div>

      {/* 訂閱詳細資訊 */}
      <div className="space-y-1 mb-3">
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span className="text-gray-400">每日發送時間</span>
          <span className="font-medium">{localSendTime}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span className="text-gray-400">語速</span>
          <span className="font-medium">{subscription.audio_speed}x</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span className="text-gray-400">建立時間</span>
          <span className="font-medium">{formattedCreatedAt}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span className="text-gray-400">無新影片</span>
          <NoDaysCounter
            noDays={subscription.no_new_video_days}
            limit={subscription.auto_cancel_days}
          />
        </div>
      </div>

      {/* 取消訂閱按鈕 */}
      <button
        type="button"
        onClick={() => onDelete(subscription.id, subscription.channel_name)}
        disabled={isDeleting}
        className="w-full text-xs font-medium py-2 px-3 rounded-md border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isDeleting ? '取消中...' : '取消訂閱'}
      </button>
    </div>
  );
}

// ===================== 主頁面元件 =====================

/**
 * 公開訂閱查詢頁面主元件
 * 提供三種視圖狀態：初始（未查詢）、查詢中（loading）、查詢後（有結果/無結果/錯誤）
 * 訂閱刪除後直接更新本地 state，不重新呼叫 API，降低網路請求數
 */
export function PublicSubscriptionListPage() {
  const [state, setState] = useState<PageState>({
    email: '',
    subscriptions: null,
    isLoading: false,
    error: null,
    deletingId: null,
    successMessage: null,
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SearchFormData>({
    resolver: zodResolver(searchSchema),
    defaultValues: { email: '' },
  });

  /**
   * 執行 Email 查詢
   * 呼叫 GET /public/subscriptions?email=xxx，成功後更新訂閱清單
   * 任何網路錯誤均捕捉並轉換為友善錯誤訊息顯示給用戶
   */
  async function handleSearch(formData: SearchFormData): Promise<void> {
    setState((prev) => ({
      ...prev,
      email: formData.email,
      isLoading: true,
      error: null,
      subscriptions: null,
      successMessage: null,
    }));

    try {
      const result = await getPublicSubscriptions(formData.email);
      setState((prev) => ({
        ...prev,
        subscriptions: result,
        isLoading: false,
      }));
    } catch (err: unknown) {
      let errorMessage = '查詢失敗，請稍後再試';
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 422) {
          errorMessage = '請確認 Email 格式正確';
        } else if (!err.response) {
          errorMessage = '無法連線至伺服器，請確認網路連線';
        }
      }
      setState((prev) => ({
        ...prev,
        error: errorMessage,
        isLoading: false,
      }));
    }
  }

  /**
   * 確認後刪除指定訂閱
   * 先以 window.confirm 取得用戶確認，避免誤觸刪除操作
   * 成功後直接從本地 state 移除該筆訂閱，並顯示短暫成功提示
   */
  async function handleDelete(id: string, channelName: string): Promise<void> {
    const confirmed = window.confirm(
      `確定要取消訂閱「${channelName}」嗎？取消後需重新訂閱。`
    );
    if (!confirmed) return;

    setState((prev) => ({ ...prev, deletingId: id, successMessage: null }));

    try {
      await deletePublicSubscription(id, state.email);
      setState((prev) => ({
        ...prev,
        deletingId: null,
        subscriptions: prev.subscriptions?.filter((s) => s.id !== id) ?? null,
        successMessage: `已成功取消訂閱「${channelName}」`,
      }));
    } catch {
      setState((prev) => ({
        ...prev,
        deletingId: null,
        error: `取消訂閱失敗，請稍後再試`,
      }));
    }
  }

  const hasResults = state.subscriptions !== null;
  const isEmpty = hasResults && state.subscriptions!.length === 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div
        className="mx-auto px-4 py-8"
        style={{ maxWidth: '640px' }}
      >
        {/* 頁首：標題、說明與導覽連結 */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs font-bold tracking-widest text-gray-400 uppercase">DailyCast</div>
            <Link
              to="/"
              className="text-xs text-gray-500 hover:text-gray-700 underline"
            >
              訂閱新頻道
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">查看我的訂閱</h1>
          <p className="text-gray-500 text-sm">
            輸入您訂閱時使用的 Email，查看並管理您的訂閱。
          </p>
        </div>

        {/* Email 查詢表單 */}
        <div className="bg-white rounded-lg border p-5 mb-5" style={{ borderColor: '#efefef', boxShadow: '0 2px 12px rgba(0,0,0,0.05)' }}>
          <form onSubmit={handleSubmit(handleSearch)} className="flex gap-3">
            <div className="flex-1">
              <input
                type="email"
                {...register('email')}
                placeholder="your@email.com"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                aria-label="訂閱 Email"
              />
              {errors.email && (
                <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={isSubmitting || state.isLoading}
              className="flex-shrink-0 bg-red-600 text-white text-sm font-medium px-4 py-2 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting || state.isLoading ? (
                <span className="flex items-center gap-1">
                  <svg
                    className="animate-spin h-4 w-4"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  查詢中
                </span>
              ) : (
                '查詢'
              )}
            </button>
          </form>
        </div>

        {/* 錯誤訊息 */}
        {state.error && (
          <div className="bg-red-50 border border-red-200 rounded-md px-4 py-3 mb-4">
            <p className="text-red-600 text-sm">{state.error}</p>
          </div>
        )}

        {/* 刪除成功訊息 */}
        {state.successMessage && (
          <div className="bg-green-50 border border-green-200 rounded-md px-4 py-3 mb-4">
            <p className="text-green-700 text-sm">{state.successMessage}</p>
          </div>
        )}

        {/* 查詢結果：無訂閱 */}
        {isEmpty && (
          <div className="bg-white rounded-lg border p-8 text-center" style={{ borderColor: '#efefef' }}>
            <div className="text-4xl mb-3">📭</div>
            <p className="text-gray-600 font-medium mb-1">此 Email 尚未訂閱任何頻道</p>
            <p className="text-gray-400 text-sm mb-4">前往首頁訂閱您喜愛的 YouTube 頻道</p>
            <Link
              to="/"
              className="inline-flex items-center gap-2 bg-red-600 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-red-700 transition-colors"
            >
              立即訂閱
            </Link>
          </div>
        )}

        {/* 查詢結果：訂閱清單 */}
        {!isEmpty && hasResults && state.subscriptions && (
          <div>
            <p className="text-xs text-gray-400 mb-3">
              共 {state.subscriptions.length} 筆訂閱（{state.email}）
            </p>
            <div className="space-y-3">
              {state.subscriptions.map((subscription) => (
                <PublicSubscriptionCard
                  key={subscription.id}
                  subscription={subscription}
                  onDelete={handleDelete}
                  isDeleting={state.deletingId === subscription.id}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
