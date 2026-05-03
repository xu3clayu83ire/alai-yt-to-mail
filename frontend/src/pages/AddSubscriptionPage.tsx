/**
 * 公開訂閱頁面（兩步驟流程，無需登入）
 * 步驟 1：輸入頻道 URL 並呼叫 /channels/verify 確認頻道資訊
 * 步驟 2：填寫訂閱設定後呼叫公開 API 送出，send_time 在送出前換算為 UTC
 * 成功後顯示確認訊息，提供「再訂閱一個」與「查看我的訂閱」操作入口
 */

import { useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { verifyChannel } from '../api/channels';
import { publicSubscribe } from '../api/public';
import type { ChannelVerifyResponse } from '../types';
import { localTimeToUtc } from '../utils/timezone';

/** 步驟 1：頻道 URL 驗證表單 schema */
const channelUrlSchema = z.object({
  channel_url: z.string().url('請輸入有效的 URL 格式'),
});

/** 步驟 2：訂閱設定表單 schema（含公開版新增欄位）
 * auto_cancel_days 在表單層保持 string 型別（HTML number input 傳出 string），
 * 驗證階段確認為有效整數且 >= 1，送出時在 handler 內 parseInt 轉換為 number
 * 此方式迴避 z.preprocess 導致 zodResolver 泛型推斷為 unknown 的已知問題
 */
const step2Schema = z.object({
  recipient_email: z.string().email('請輸入有效的 Email 格式'),
  audio_speed: z.enum(['0.5', '0.75', '0.85', '1.0', '1.5', '2.0']),
  send_time: z.string().regex(/^\d{2}:\d{2}$/, '時間格式錯誤'),
  auto_cancel_days: z
    .string()
    .min(1, '請輸入天數')
    .refine((val) => /^\d+$/.test(val) && parseInt(val, 10) >= 1, '至少 1 天，請輸入正整數'),
});

type ChannelUrlFormData = z.infer<typeof channelUrlSchema>;
type Step2FormData = z.infer<typeof step2Schema>;

/**
 * 根據 HTTP 狀態碼與回應內容對應友善錯誤訊息
 * 區分上限錯誤、驗證錯誤與一般伺服器錯誤，協助用戶快速理解問題
 */
function resolveSubmitError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail: string = error.response?.data?.detail ?? '';

    if (status === 400) {
      if (detail.includes('上限')) return '此信箱已達 5 個訂閱上限';
      return '無法識別此頻道 URL，請確認格式';
    }
    if (status === 422) return '請確認欄位填寫正確';
  }
  return '送出失敗，請稍後再試';
}

/**
 * 公開訂閱頁面元件
 * 兩步驟設計確保用戶確認頻道後再填寫設定，減少錯誤訂閱的可能
 * 不依賴 JWT，適合未登入用戶直接使用
 */
export function AddSubscriptionPage() {
  const formRef = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState<1 | 2 | 'success'>(1);
  const [verifiedChannel, setVerifiedChannel] = useState<ChannelVerifyResponse | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successEmail, setSuccessEmail] = useState<string>('');

  /** 步驟 1 表單 */
  const channelForm = useForm<ChannelUrlFormData>({
    resolver: zodResolver(channelUrlSchema),
    defaultValues: {
      channel_url: 'https://www.youtube.com/@melrobbins',
    },
  });

  /** 步驟 2 表單 */
  const subscriptionForm = useForm<Step2FormData>({
    resolver: zodResolver(step2Schema),
    defaultValues: {
      recipient_email: '',
      audio_speed: '1.0',
      send_time: '09:00',
      auto_cancel_days: '3',
    },
  });

  /**
   * 處理步驟 1：呼叫頻道驗證 API
   * 成功後保存頻道資訊並進入步驟 2，失敗顯示友善錯誤訊息
   */
  const handleVerifyChannel = async (data: ChannelUrlFormData) => {
    setVerifyError(null);
    try {
      const result = await verifyChannel({ channel_url: data.channel_url });
      setVerifiedChannel(result);
      setStep(2);
    } catch {
      setVerifyError('無法識別此頻道 URL，請確認格式');
    }
  };

  /**
   * 處理步驟 2：呼叫公開訂閱 API
   * send_time 在送出前從本地時間換算為 UTC，確保後端儲存正確時間
   * 成功後切換至成功狀態顯示確認訊息
   */
  const handleSubmitSubscription = async (data: Step2FormData) => {
    if (!verifiedChannel) return;
    setSubmitError(null);

    try {
      const utcSendTime = localTimeToUtc(data.send_time);
      await publicSubscribe({
        recipient_email: data.recipient_email,
        channel_url: verifiedChannel.channel_url,
        audio_speed: parseFloat(data.audio_speed),
        send_time: utcSendTime,
        auto_cancel_days: parseInt(data.auto_cancel_days, 10),
      });
      setSuccessEmail(data.recipient_email);
      setStep('success');
    } catch (error: unknown) {
      setSubmitError(resolveSubmitError(error));
    }
  };

  /**
   * 重置表單回初始狀態，讓用戶可以繼續新增下一個訂閱
   * 清除所有暫存資料與狀態，確保不殘留上一次的填寫內容
   */
  const handleReset = () => {
    channelForm.reset({ channel_url: '' });
    subscriptionForm.reset({
      recipient_email: '',
      audio_speed: '1.0',
      send_time: '09:00',
      auto_cancel_days: '3',
    });
    setVerifiedChannel(null);
    setVerifyError(null);
    setSubmitError(null);
    setSuccessEmail('');
    setStep(1);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* 原型聲明 Banner */}
      <div className="bg-amber-50 border-2 border-amber-400 rounded-lg px-4 py-3 mb-6 text-center">
        <p className="text-amber-800 font-bold text-sm">⚠️ 這是個人原型 Demo，非商業服務</p>
        <p className="text-amber-700 text-xs mt-1">此網站用於功能測試，不會蒐集或販售任何個人資料</p>
      </div>

      {/* Hero 區塊 */}
      <div className="mb-8 text-center">
        <div className="text-xs font-bold tracking-widest text-gray-400 uppercase mb-2">DailyCast</div>
        <span
          className="inline-block text-xs font-semibold px-3 py-1 rounded-full mb-4 text-white"
          style={{ background: 'linear-gradient(135deg, #f97316, #ec4899)' }}
        >
          專為忙碌上班族打造的微學習服務
        </span>
        <h1
          className="font-bold text-gray-900 mb-3 leading-tight"
          style={{ fontSize: 'clamp(26px, 5vw, 42px)' }}
        >
          每天 60 秒，<br />
          <span style={{ background: 'linear-gradient(135deg, #f97316, #ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            無痛養成辦公室英語語感
          </span>
        </h1>
        <p className="text-gray-500 mx-auto" style={{ fontSize: '16px', lineHeight: '1.7', maxWidth: '520px' }}>
          訂閱喜愛的頻道，每日自動萃取 60 秒精華音檔與逐字稿。
          無需額外安排時間，讓聽力練習自然融入通勤日常。
        </p>
      </div>

      {/* Feature 卡片 */}
      <div className="grid gap-3 mb-8" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        {[
          {
            icon: '📬',
            title: '智慧遞送｜零操作負擔',
            desc: '每天定時自動送達信箱，省去在 YouTube 大海撈針的時間。打開信件即可開始練習。',
          },
          {
            icon: '🎵',
            title: '黃金 60 秒｜隨心調整語速',
            desc: 'AI 精準擷取核心片段，支援 0.75x 到 1.5x 多段語速自訂。細品發音或快速複習，完美配合節奏。',
          },
          {
            icon: '📝',
            title: '智能逐字稿｜視聽雙重吸收',
            desc: '搭載先進 AI 轉錄技術，提供精準文字稿對照。即使不方便開聲音，也能透過閱讀輕鬆吸收。',
          },
        ].map(({ icon, title, desc }) => (
          <div
            key={title}
            className="bg-white p-4 transition-all"
            style={{
              border: '1px solid #efefef',
              borderRadius: '16px',
              boxShadow: '0 4px 40px rgba(0,0,0,0.06)',
            }}
          >
            <div className="text-2xl mb-2">{icon}</div>
            <div className="text-sm font-semibold text-gray-800 mb-1">{title}</div>
            <div className="text-xs text-gray-500" style={{ lineHeight: '1.6' }}>{desc}</div>
          </div>
        ))}
      </div>

      {/* CTA 區塊 */}
      <div
        className="mb-8 text-center p-8"
        style={{
          background: 'linear-gradient(135deg, rgba(249,115,22,0.06), rgba(236,72,153,0.06))',
          border: '1px solid rgba(249,115,22,0.15)',
          borderRadius: '20px',
        }}
      >
        <h2 className="font-bold text-gray-900 mb-2" style={{ fontSize: '20px' }}>
          開啟您的每日英語早晨
        </h2>
        <p className="text-gray-500 mb-5" style={{ fontSize: '15px', lineHeight: '1.7' }}>
          只要輸入 YouTube 頻道網址，即可在信箱中開啟專屬英語練習。
        </p>
        <button
          type="button"
          onClick={() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          className="inline-flex items-center gap-2 text-white font-semibold px-6 py-3 transition-opacity hover:opacity-90"
          style={{
            background: 'linear-gradient(135deg, #f97316, #ec4899)',
            borderRadius: '999px',
            fontSize: '15px',
          }}
        >
          👉 馬上輸入頻道網址，免費體驗
        </button>
      </div>

      {/* 成功狀態：訂閱完成確認訊息 */}
      {step === 'success' && (
        <div
          ref={formRef}
          className="bg-white rounded-lg shadow-sm border p-8 text-center"
        >
          <div className="text-5xl mb-4">🎉</div>
          <h3 className="font-bold text-gray-900 text-xl mb-2">訂閱成功！</h3>
          <p className="text-gray-600 mb-1">
            精華音檔將每日發送至
          </p>
          <p className="font-semibold text-red-600 mb-6 break-all">{successEmail}</p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center justify-center gap-2 bg-red-600 text-white font-semibold px-6 py-3 rounded-lg hover:bg-red-700 transition-colors"
            >
              再訂閱一個
            </button>
            <Link
              to="/my-subscriptions"
              className="inline-flex items-center justify-center gap-2 bg-gray-100 text-gray-700 font-semibold px-6 py-3 rounded-lg hover:bg-gray-200 transition-colors"
            >
              查看我的訂閱
            </Link>
          </div>
        </div>
      )}

      {/* 步驟指示器（僅在步驟 1 與 2 顯示）*/}
      {step !== 'success' && (
        <>
          <div ref={formRef} className="flex items-center gap-2 mb-6">
            <div className={`flex items-center justify-center w-7 h-7 rounded-full text-sm font-medium ${step === 1 ? 'bg-red-600 text-white' : 'bg-green-500 text-white'}`}>
              {step === 1 ? '1' : '✓'}
            </div>
            <span className={`text-sm ${step === 1 ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>確認頻道</span>
            <div className="flex-1 h-px bg-gray-200" />
            <div className={`flex items-center justify-center w-7 h-7 rounded-full text-sm font-medium ${step === 2 ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              2
            </div>
            <span className={`text-sm ${step === 2 ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>填寫設定</span>
          </div>

          {/* 步驟 1：輸入頻道 URL */}
          {step === 1 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-medium text-gray-900 mb-4">步驟 1：確認 YouTube 頻道</h3>
              <form onSubmit={channelForm.handleSubmit(handleVerifyChannel)} className="space-y-4">
                <div>
                  <label htmlFor="channel_url" className="block text-sm font-medium text-gray-700 mb-1">
                    頻道 URL
                  </label>
                  <input
                    id="channel_url"
                    type="text"
                    {...channelForm.register('channel_url')}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="https://www.youtube.com/@channelname"
                  />
                  {channelForm.formState.errors.channel_url && (
                    <p className="text-red-500 text-xs mt-1">{channelForm.formState.errors.channel_url.message}</p>
                  )}
                </div>

                {verifyError && (
                  <div className="bg-red-50 border border-red-200 rounded-md px-3 py-2">
                    <p className="text-red-600 text-sm">{verifyError}</p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={channelForm.formState.isSubmitting}
                  className="w-full bg-red-600 text-white py-2 px-4 rounded-md font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  {channelForm.formState.isSubmitting ? '確認中...' : '確認頻道'}
                </button>
              </form>
            </div>
          )}

          {/* 步驟 2：填寫訂閱設定 */}
          {step === 2 && verifiedChannel && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-medium text-gray-900 mb-4">步驟 2：填寫訂閱設定</h3>

              {/* 已確認的頻道資訊（唯讀）*/}
              <div className="bg-gray-50 rounded-md p-3 mb-4">
                <p className="text-xs text-gray-500 mb-1">已確認頻道</p>
                <p className="font-medium text-gray-900">{verifiedChannel.channel_name}</p>
                <a
                  href={verifiedChannel.channel_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-500 hover:underline"
                >
                  {verifiedChannel.channel_url}
                </a>
              </div>

              <form onSubmit={subscriptionForm.handleSubmit(handleSubmitSubscription)} className="space-y-4">
                {/* 收件信箱 */}
                <div>
                  <label htmlFor="recipient_email" className="block text-sm font-medium text-gray-700 mb-1">
                    收件信箱
                  </label>
                  <input
                    id="recipient_email"
                    type="email"
                    {...subscriptionForm.register('recipient_email')}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="your@email.com"
                  />
                  {subscriptionForm.formState.errors.recipient_email && (
                    <p className="text-red-500 text-xs mt-1">{subscriptionForm.formState.errors.recipient_email.message}</p>
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
                    {...subscriptionForm.register('send_time')}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                  {subscriptionForm.formState.errors.send_time && (
                    <p className="text-red-500 text-xs mt-1">{subscriptionForm.formState.errors.send_time.message}</p>
                  )}
                </div>

                {/* 語速選擇 */}
                <div>
                  <label htmlFor="audio_speed" className="block text-sm font-medium text-gray-700 mb-1">
                    語速
                  </label>
                  <select
                    id="audio_speed"
                    {...subscriptionForm.register('audio_speed')}
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

                {/* 自動取消天數 */}
                <div>
                  <label htmlFor="auto_cancel_days" className="block text-sm font-medium text-gray-700 mb-1">
                    自動取消天數
                  </label>
                  <input
                    id="auto_cancel_days"
                    type="number"
                    min={1}
                    step={1}
                    {...subscriptionForm.register('auto_cancel_days')}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="3"
                  />
                  <p className="text-xs text-gray-400 mt-1">頻道連續 N 天無新影片時，自動取消此訂閱</p>
                  {subscriptionForm.formState.errors.auto_cancel_days && (
                    <p className="text-red-500 text-xs mt-1">{subscriptionForm.formState.errors.auto_cancel_days.message}</p>
                  )}
                </div>

                {submitError && (
                  <div className="bg-red-50 border border-red-200 rounded-md px-3 py-2">
                    <p className="text-red-600 text-sm">{submitError}</p>
                  </div>
                )}

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="flex-1 bg-gray-100 text-gray-700 py-2 px-4 rounded-md font-medium hover:bg-gray-200 transition-colors"
                  >
                    返回
                  </button>
                  <button
                    type="submit"
                    disabled={subscriptionForm.formState.isSubmitting}
                    className="flex-1 bg-red-600 text-white py-2 px-4 rounded-md font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    {subscriptionForm.formState.isSubmitting ? '建立中...' : '建立訂閱'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </>
      )}
    </div>
  );
}
