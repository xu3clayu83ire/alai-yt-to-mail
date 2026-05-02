/**
 * 受保護路由元件
 * 確保只有已登入用戶才能存取需要認證的頁面
 * 未登入時自動重導至登入頁，保護敏感資源
 */

import { Navigate } from 'react-router-dom';
import { getToken } from '../utils/storage';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * 路由保護 Wrapper 元件
 * 檢查 localStorage token 是否存在，未登入則立即 redirect 到 /login
 * 使用 replace 避免將受保護路由加入瀏覽器歷史，防止按上一頁繞過保護
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const token = getToken();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
