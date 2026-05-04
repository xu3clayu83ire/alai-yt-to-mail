/**
 * 管理員頻道管理 API 呼叫函式模組
 * 所有請求需帶 admin JWT（從 localStorage 的 adminToken 取得）
 * 不使用共用的 apiClient，避免 401 攔截器觸發一般用戶的登出邏輯
 * 401/403 回應時清除 admin token 並拋出錯誤，由頁面元件負責跳轉
 */

import axios from 'axios';
import { getAdminToken, removeAdminToken } from '../utils/storage';
import type {
  ChannelItem,
  ChannelCreateRequest,
  ChannelUpdateRequest,
  ChannelDeleteResponse,
} from '../types';

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
 * 建立新頻道
 * 對應後端 POST /admin/channels，傳入 channel_id、channel_name、channel_url
 * 409 衝突表示 channel_id 已存在，由頁面元件自行判斷並顯示友善訊息
 */
export async function adminCreateChannel(data: ChannelCreateRequest): Promise<ChannelItem> {
  try {
    const response = await axios.post<ChannelItem>(
      `${import.meta.env.VITE_API_BASE_URL}/admin/channels`,
      data,
      {
        headers: {
          'Content-Type': 'application/json',
          ...adminHeaders(),
        },
      }
    );
    return response.data;
  } catch (error: unknown) {
    return handleAuthError(error);
  }
}

/**
 * 查詢所有頻道列表
 * 對應後端 GET /admin/channels，回傳含建立時間的完整頻道資訊
 */
export async function adminListChannels(): Promise<ChannelItem[]> {
  try {
    const response = await axios.get<ChannelItem[]>(
      `${import.meta.env.VITE_API_BASE_URL}/admin/channels`,
      {
        headers: {
          'Content-Type': 'application/json',
          ...adminHeaders(),
        },
      }
    );
    return response.data;
  } catch (error: unknown) {
    return handleAuthError(error);
  }
}

/**
 * 更新指定頻道資訊
 * 對應後端 PUT /admin/channels/{channelId}，channel_id 不可修改
 * 僅允許更新 channel_name 與 channel_url
 */
export async function adminUpdateChannel(
  channelId: string,
  data: ChannelUpdateRequest
): Promise<ChannelItem> {
  try {
    const response = await axios.put<ChannelItem>(
      `${import.meta.env.VITE_API_BASE_URL}/admin/channels/${channelId}`,
      data,
      {
        headers: {
          'Content-Type': 'application/json',
          ...adminHeaders(),
        },
      }
    );
    return response.data;
  } catch (error: unknown) {
    return handleAuthError(error);
  }
}

/**
 * 刪除指定頻道
 * 對應後端 DELETE /admin/channels/{channelId}
 * 刪除後後端會同時取消所有訂閱此頻道的用戶並發送通知，回傳受影響訂閱數
 */
export async function adminDeleteChannel(channelId: string): Promise<ChannelDeleteResponse> {
  try {
    const response = await axios.delete<ChannelDeleteResponse>(
      `${import.meta.env.VITE_API_BASE_URL}/admin/channels/${channelId}`,
      {
        headers: {
          'Content-Type': 'application/json',
          ...adminHeaders(),
        },
      }
    );
    return response.data;
  } catch (error: unknown) {
    return handleAuthError(error);
  }
}
