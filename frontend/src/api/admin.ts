/**
 * 管理員 API 呼叫函式模組
 * 所有請求需帶 admin JWT（從 getAdminToken() 取得）
 * 不使用共用的 apiClient，避免 401 攔截器觸發一般用戶的登出邏輯
 * 401/403 回應時清除 admin token 並拋出錯誤，由頁面元件負責跳轉
 */

import axios from 'axios';
import { getAdminToken, removeAdminToken } from '../utils/storage';
import type { AdminSubscriptionItem } from '../types';

/**
 * 建立帶 admin JWT 的 axios 請求 headers
 * 若 token 不存在則回傳空物件（後端會回應 401/403）
 */
function adminHeaders(): Record<string, string> {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * 處理管理員 API 的認證錯誤
 * 收到 401 或 403 時清除 admin token，讓頁面元件捕捉後跳轉至登入頁
 * 此函式集中處理清除邏輯，避免在各 API 函式重複撰寫
 */
function handleAuthError(error: unknown): never {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 401 || status === 403) {
      removeAdminToken();
      throw new Error('AUTH_EXPIRED');
    }
  }
  throw error;
}

/**
 * 查詢所有訂閱（可選 email 篩選）
 * 後端 GET /admin/subscriptions 支援 ?email= 參數進行全文符合篩選
 */
export async function adminListSubscriptions(
  email?: string
): Promise<AdminSubscriptionItem[]> {
  try {
    const params: Record<string, string> = {};
    if (email && email.trim() !== '') {
      params.email = email.trim();
    }
    const response = await axios.get<AdminSubscriptionItem[]>(
      `${import.meta.env.VITE_API_BASE_URL}/admin/subscriptions`,
      {
        headers: {
          'Content-Type': 'application/json',
          ...adminHeaders(),
        },
        params,
      }
    );
    return response.data;
  } catch (error: unknown) {
    return handleAuthError(error);
  }
}

/**
 * 刪除指定訂閱（admin 強制刪除，不檢查擁有者）
 * 對應後端 DELETE /admin/subscriptions/{id}
 */
export async function adminDeleteSubscription(id: string): Promise<void> {
  try {
    await axios.delete(
      `${import.meta.env.VITE_API_BASE_URL}/admin/subscriptions/${id}`,
      {
        headers: {
          'Content-Type': 'application/json',
          ...adminHeaders(),
        },
      }
    );
  } catch (error: unknown) {
    return handleAuthError(error);
  }
}
