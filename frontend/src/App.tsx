/**
 * 應用程式根元件，設定 React Router 路由規則
 * 根路由（/）改為公開訂閱頁，無需登入即可使用
 * 受保護路由（管理功能）仍需 JWT 驗證
 * 管理員後台路由（/admin/*）使用獨立的 AdminRoute 守衛，與一般用戶 token 分開
 * TanStack Query 的 QueryClient 在此層提供，確保全域資料快取共享
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AdminRoute } from './components/AdminRoute';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { SubscriptionListPage } from './pages/SubscriptionListPage';
import { AddSubscriptionPage } from './pages/AddSubscriptionPage';
import { EditSubscriptionPage } from './pages/EditSubscriptionPage';
import { HistoryPage } from './pages/HistoryPage';
import { AdminLoginPage } from './pages/AdminLoginPage';
import { AdminSubscriptionsPage } from './pages/AdminSubscriptionsPage';
import { getToken } from './utils/storage';
import { PublicSubscriptionListPage } from './pages/PublicSubscriptionListPage';

/**
 * 建立 QueryClient 實例，設定合理的預設值
 * staleTime 設為 30 秒，避免頻繁重新請求
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 1,
    },
  },
});

/**
 * 公開路由 Guard：已登入時自動重導至首頁
 * 防止已登入用戶重複存取登入/註冊頁
 */
function PublicRoute({ children }: { children: React.ReactNode }) {
  const token = getToken();
  if (token) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

/**
 * 主要 App 元件，包含路由設定與全域 Provider
 * 根路由為公開訂閱頁，讓用戶無需帳號即可體驗核心功能
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* 公開路由：未登入可訪問，已登入自動重導 */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />

          {/* 根路由：公開訂閱頁（無需登入）*/}
          <Route path="/" element={<AddSubscriptionPage />} />

          {/* /subscriptions/add：公開訂閱頁別名 */}
          <Route path="/subscriptions/add" element={<AddSubscriptionPage />} />

          {/* /my-subscriptions：公開訂閱查詢頁（無需登入）*/}
          <Route path="/my-subscriptions" element={<PublicSubscriptionListPage />} />

          {/* 受保護路由：需要登入才能訪問（管理功能）*/}
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <Layout>
                  <SubscriptionListPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subscriptions/:id/edit"
            element={
              <ProtectedRoute>
                <Layout>
                  <EditSubscriptionPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <Layout>
                  <HistoryPage />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* 管理員路由：使用 AdminRoute 守衛，與一般用戶 token 完全分離 */}
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route
            path="/admin/subscriptions"
            element={
              <AdminRoute>
                <AdminSubscriptionsPage />
              </AdminRoute>
            }
          />

          {/* 未知路徑重導至根路由 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
