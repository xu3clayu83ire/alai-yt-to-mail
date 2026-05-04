/**
 * 公開頻道列表 API 呼叫函式
 * 無需 Authorization header，供訂閱頁面載入可選頻道清單
 * 採用獨立 axios 實例，避免觸發帶有攔截器的 apiClient 認證邏輯
 */

import axios from 'axios';
import type { PublicChannelItem } from '../types';

/**
 * 取得公開頻道列表
 * 呼叫 GET /public/channels，不帶任何認證 header
 * 頻道由管理員維護，用戶僅能選擇而無法自行新增
 */
export async function getPublicChannels(): Promise<PublicChannelItem[]> {
  const response = await axios.get<PublicChannelItem[]>(
    `${import.meta.env.VITE_API_BASE_URL}/public/channels`
  );
  return response.data;
}
