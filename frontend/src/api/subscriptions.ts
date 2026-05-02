/**
 * 訂閱管理相關 API 呼叫函式
 * 封裝 CRUD 操作，確保型別安全與一致的錯誤處理
 */

import apiClient from './client';
import type { Subscription, SubscriptionCreateRequest, SubscriptionUpdateRequest } from '../types';

/**
 * 取得當前用戶的所有訂閱清單
 * 回傳陣列依後端排序，前端可直接顯示
 */
export async function getSubscriptions(): Promise<Subscription[]> {
  const response = await apiClient.get<Subscription[]>('/subscriptions');
  return response.data;
}

/**
 * 新增一筆訂閱
 * send_time 必須在呼叫前換算為 UTC HH:MM 格式
 */
export async function createSubscription(data: SubscriptionCreateRequest): Promise<Subscription> {
  const response = await apiClient.post<Subscription>('/subscriptions', data);
  return response.data;
}

/**
 * 更新指定訂閱的設定
 * 支援部分更新（partial update），僅傳送有變更的欄位
 */
export async function updateSubscription(
  id: string,
  data: SubscriptionUpdateRequest
): Promise<Subscription> {
  const response = await apiClient.put<Subscription>(`/subscriptions/${id}`, data);
  return response.data;
}

/**
 * 刪除指定訂閱
 * 呼叫前需要求用戶確認，避免誤刪
 */
export async function deleteSubscription(id: string): Promise<void> {
  await apiClient.delete(`/subscriptions/${id}`);
}
