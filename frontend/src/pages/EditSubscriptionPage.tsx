/**
 * 編輯訂閱頁面
 * 從路由參數取得訂閱 ID，呼叫 GET /subscriptions 找到對應項目預填表單
 * send_time 顯示時轉為本地時間，送出前換算回 UTC
 */

import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getSubscriptions, updateSubscription } from '../api/subscriptions';
import { localTimeToUtc, utcTimeToLocal } from '../utils/timezone';

/** 編輯訂閱表單驗證 Schema */
const editSchema = z.object({
  recipient_email: z.string().email('請輸入有效的 Email 格式'),
  audio_speed: z.enum(['0.5', '0.75', '0.85', '1.0', '1.5', '2.0']),
  send_time: z.string().regex(/^\d{2}:\d{2}$/, '時間格式錯誤'),
  is_active: z.boolean(),
});

type EditFormData = z.infer<typeof editSchema>;

/**
 * 編輯訂閱頁面元件
 * 頻道資訊唯讀顯示，僅允許修改收件信箱、時間、語速與啟用狀態
 */
export function EditSubscriptionPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  /** 取得所有訂閱以找到當前編輯項目 */
  const { data: subscriptions = [], isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: getSubscriptions,
  });

  const subscription = subscriptions.find((s) => s.id === id);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditFormData>({
    resolver: zodResolver(editSchema),
  });

  /**
   * 訂閱資料載入後預填表單
   * send_time 從 UTC 轉換為本地時間顯示，避免用戶混淆
   */
  useEffect(() => {
    if (subscription) {
      reset({
        recipient_email: subscription.recipient_email,
        audio_speed: String(subscription.audio_speed) as '0.5' | '1.0' | '1.5' | '2.0',
        send_time: utcTimeToLocal(subscription.send_time),
        is_active: subscription.is_active,
      });
    }
  }, [subscription, reset]);

  /**
   * 處理儲存操作
   * send_time 在送出前從本地時間換算回 UTC
   */
  const onSubmit = async (data: EditFormData) => {
    if (!id) return;
    const utcSendTime = localTimeToUtc(data.send_time);
    await updateSubscription(id, {
      recipient_email: data.recipient_email,
      audio_speed: parseFloat(data.audio_speed),
      send_time: utcSendTime,
      is_active: data.is_active,
    });
    navigate('/');
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <p className="text-gray-500">載入中...</p>
      </div>
    );
  }

  if (!subscription) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-red-600">找不到訂閱，請返回列表頁</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">編輯訂閱</h2>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        {/* 頻道資訊（唯讀）*/}
        <div className="bg-gray-50 rounded-md p-3 mb-6">
          <p className="text-xs text-gray-500 mb-1">頻道資訊（不可修改）</p>
          <p className="font-medium text-gray-900">{subscription.channel_name}</p>
          <a
            href={subscription.channel_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-500 hover:underline"
          >
            {subscription.channel_url}
          </a>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* 收件信箱 */}
          <div>
            <label htmlFor="recipient_email" className="block text-sm font-medium text-gray-700 mb-1">
              收件信箱
            </label>
            <input
              id="recipient_email"
              type="email"
              {...register('recipient_email')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            {errors.recipient_email && (
              <p className="text-red-500 text-xs mt-1">{errors.recipient_email.message}</p>
            )}
          </div>

          {/* 每日發送時間（本地時間）*/}
          <div>
            <label htmlFor="send_time" className="block text-sm font-medium text-gray-700 mb-1">
              每日發送時間（本地時間）
            </label>
            <input
              id="send_time"
              type="time"
              {...register('send_time')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            {errors.send_time && (
              <p className="text-red-500 text-xs mt-1">{errors.send_time.message}</p>
            )}
          </div>

          {/* 語速選擇 */}
          <div>
            <label htmlFor="audio_speed" className="block text-sm font-medium text-gray-700 mb-1">
              語速
            </label>
            <select
              id="audio_speed"
              {...register('audio_speed')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            >
              <option value="0.5">0.5x（慢速）</option>
              <option value="0.75">0.75x</option>
              <option value="0.85">0.85x</option>
              <option value="1.0">1.0x（正常）</option>
              <option value="1.5">1.5x（快速）</option>
              <option value="2.0">2.0x（極快）</option>
            </select>
          </div>

          {/* 啟用/停用切換 */}
          <div className="flex items-center gap-3">
            <input
              id="is_active"
              type="checkbox"
              {...register('is_active')}
              className="h-4 w-4 text-red-600 rounded border-gray-300 focus:ring-red-500"
            />
            <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
              啟用此訂閱
            </label>
          </div>

          {/* 操作按鈕 */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="flex-1 bg-gray-100 text-gray-700 py-2 px-4 rounded-md font-medium hover:bg-gray-200 transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 bg-red-600 text-white py-2 px-4 rounded-md font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? '儲存中...' : '儲存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
