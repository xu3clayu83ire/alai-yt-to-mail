/**
 * 訂閱卡片元件
 * 顯示單一訂閱的所有資訊，提供啟用/停用切換、編輯與刪除操作
 * send_time 在此元件內從 UTC 轉換為本地時間顯示
 */

import { Link } from 'react-router-dom';
import type { Subscription } from '../types';
import { utcTimeToLocal } from '../utils/timezone';

interface SubscriptionCardProps {
  subscription: Subscription;
  onToggleActive: (id: string, isActive: boolean) => void;
  onDelete: (id: string, channelName: string) => void;
}

/**
 * 訂閱卡片顯示元件
 * 啟用/停用切換即時回呼父元件，不在此處直接呼叫 API 確保資料流清晰
 */
export function SubscriptionCard({ subscription, onToggleActive, onDelete }: SubscriptionCardProps) {
  const localSendTime = utcTimeToLocal(subscription.send_time);

  return (
    <div className={`bg-white rounded-lg shadow-sm border p-4 ${!subscription.is_active ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between">
        {/* 頻道資訊 */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">{subscription.channel_name}</h3>
          <a
            href={subscription.channel_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-500 hover:underline truncate block"
          >
            {subscription.channel_url}
          </a>
        </div>

        {/* 啟用/停用開關 */}
        <div className="ml-4 flex-shrink-0">
          <button
            onClick={() => onToggleActive(subscription.id, !subscription.is_active)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
              subscription.is_active ? 'bg-green-500' : 'bg-gray-300'
            }`}
            aria-label={subscription.is_active ? '停用訂閱' : '啟用訂閱'}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                subscription.is_active ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* 訂閱設定資訊 */}
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-gray-600">
        <div>
          <span className="text-gray-400">收件信箱：</span>
          <span className="truncate">{subscription.recipient_email}</span>
        </div>
        <div>
          <span className="text-gray-400">語速：</span>
          <span>{subscription.audio_speed}x</span>
        </div>
        <div>
          <span className="text-gray-400">每日發送：</span>
          <span>{localSendTime}（本地時間）</span>
        </div>
        <div>
          <span className="text-gray-400">狀態：</span>
          <span className={subscription.is_active ? 'text-green-600' : 'text-gray-400'}>
            {subscription.is_active ? '啟用中' : '已停用'}
          </span>
        </div>
      </div>

      {/* 操作按鈕 */}
      <div className="mt-3 flex gap-2">
        <Link
          to={`/subscriptions/${subscription.id}/edit`}
          className="flex-1 text-center text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 py-1.5 px-3 rounded-md transition-colors"
        >
          編輯
        </Link>
        <button
          onClick={() => onDelete(subscription.id, subscription.channel_name)}
          className="flex-1 text-sm bg-red-50 hover:bg-red-100 text-red-600 py-1.5 px-3 rounded-md transition-colors"
        >
          刪除
        </button>
      </div>
    </div>
  );
}
