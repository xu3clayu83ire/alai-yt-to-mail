/**
 * 歷史紀錄相關 API 呼叫函式
 * 支援分頁載入，避免一次載入大量資料影響效能
 */

import apiClient from './client';
import type { HistoryItem } from '../types';

/**
 * 取得歷史紀錄清單（分頁）
 * limit 控制每次載入筆數，offset 支援「載入更多」功能的累加邏輯
 */
export async function getHistory(limit: number, offset: number): Promise<HistoryItem[]> {
  const response = await apiClient.get<HistoryItem[]>('/history', {
    params: { limit, offset },
  });
  return response.data;
}
