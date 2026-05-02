/**
 * 頻道確認相關 API 呼叫函式
 * 在新增訂閱前先驗證頻道 URL 的有效性，取得頻道名稱與 ID
 */

import apiClient from './client';
import type { ChannelVerifyRequest, ChannelVerifyResponse } from '../types';

/**
 * 驗證 YouTube 頻道 URL 並取得頻道資訊
 * 成功後回傳 channel_id 與 channel_name 供新增訂閱步驟使用
 */
export async function verifyChannel(data: ChannelVerifyRequest): Promise<ChannelVerifyResponse> {
  const response = await apiClient.post<ChannelVerifyResponse>('/channels/verify', data);
  return response.data;
}
