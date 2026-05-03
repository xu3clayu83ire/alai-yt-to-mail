/**
 * 公開 API 呼叫函式模組（無需 JWT）
 * 對應後端 /public/* 端點，允許未登入用戶直接訂閱與查詢
 * 使用共用的 apiClient，但後端不會驗證 Authorization header
 */
import apiClient from './client';

/** 公開訂閱請求格式（send_time 為 UTC HH:MM）*/
export interface PublicSubscribeRequest {
  recipient_email: string;
  channel_url: string;
  audio_speed: number;
  send_time: string;
  auto_cancel_days: number;
}

/** 公開訂閱回應格式 */
export interface PublicSubscriptionResponse {
  id: string;
  channel_url: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
  is_active: boolean;
  auto_cancel_days: number;
  no_new_video_days: number;
  created_at: string;
}

/**
 * 公開訂閱：無需登入直接送出訂閱請求
 * 後端以 email 作為用戶識別，不需要帳號系統即可使用
 */
export async function publicSubscribe(
  data: PublicSubscribeRequest
): Promise<PublicSubscriptionResponse> {
  const response = await apiClient.post<PublicSubscriptionResponse>('/public/subscribe', data);
  return response.data;
}

/**
 * 以 email 查詢訂閱清單
 * 公開端點讓用戶無需登入即可查閱自己的訂閱狀態
 */
export async function getPublicSubscriptions(
  email: string
): Promise<PublicSubscriptionResponse[]> {
  const response = await apiClient.get<PublicSubscriptionResponse[]>('/public/subscriptions', {
    params: { email },
  });
  return response.data;
}

/**
 * 以 email 驗證身分後刪除指定訂閱
 * 透過 email 參數確認操作者身分，防止任意刪除他人訂閱
 */
export async function deletePublicSubscription(id: string, email: string): Promise<void> {
  await apiClient.delete(`/public/subscriptions/${id}`, { params: { email } });
}
