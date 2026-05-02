/**
 * axios HTTP 客戶端實例
 * 集中設定 baseURL、timeout 與攔截器，確保所有 API 呼叫一致性
 * Request 攔截器自動附加 JWT，Response 攔截器處理 401 自動登出
 */

import axios from 'axios';
import { getToken, removeToken } from '../utils/storage';

/**
 * 建立 axios 實例，統一設定後端 API 連線參數
 * baseURL 從 Vite 環境變數讀取，支援多環境部署
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request 攔截器：自動從 localStorage 取得 JWT 並附加 Authorization header
 * 確保所有需要認證的 API 呼叫都能正確傳送 token，無需在每個呼叫處手動設定
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: unknown) => {
    return Promise.reject(error);
  }
);

/**
 * Response 攔截器：統一處理 HTTP 401 未授權回應
 * 收到 401 時清除本地 token 並重導至登入頁，防止用戶以過期 token 繼續操作
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      removeToken();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
