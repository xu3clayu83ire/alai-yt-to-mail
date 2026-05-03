/**
 * 管理員路由守衛元件
 * 驗證 admin token 存在，不存在時重導至 /admin/login
 * 僅驗證 token 是否存在於 localStorage，不主動解碼 JWT payload
 * 實際權限驗證依賴後端 API 回應的 403 錯誤，由頁面元件負責處理跳轉
 * 此設計確保 admin 路由與一般用戶路由（ProtectedRoute）完全分離，互不干擾
 */

import { Navigate } from 'react-router-dom';
import type { ReactElement } from 'react';
import { getAdminToken } from '../utils/storage';

interface AdminRouteProps {
  children: React.ReactNode;
}

/**
 * 管理員路由 Wrapper 元件
 * 檢查 admin_access_token 是否存在，未登入則立即 redirect 到 /admin/login
 * 使用 replace 避免將受保護路由加入瀏覽器歷史，防止按上一頁繞過保護
 */
export function AdminRoute({ children }: AdminRouteProps): ReactElement {
  const token = getAdminToken();

  if (!token) {
    return <Navigate to="/admin/login" replace />;
  }

  return <>{children}</>;
}
