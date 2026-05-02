/**
 * 認證狀態管理 Hook
 * 提供全域認證狀態讀取與登出操作，避免各元件直接操作 localStorage
 */

import { useNavigate } from 'react-router-dom';
import { getToken, removeToken } from '../utils/storage';

/**
 * 提供認證相關狀態與操作的 custom hook
 * isAuthenticated 根據 localStorage token 是否存在判斷登入狀態
 * logout 清除 token 並重導至登入頁，確保安全退出
 */
export function useAuth() {
  const navigate = useNavigate();

  /** 根據 token 是否存在判斷用戶是否已登入 */
  const isAuthenticated = getToken() !== null;

  /**
   * 執行登出操作
   * 清除本地 token 後重導至登入頁，防止用戶繼續存取受保護資源
   */
  const logout = () => {
    removeToken();
    navigate('/login');
  };

  return { isAuthenticated, logout };
}
