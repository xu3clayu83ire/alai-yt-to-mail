/**
 * 應用程式根元件，設定 React Router 路由規則
 * 區分公開路由（登入/註冊）與受保護路由（需要登入）
 * TanStack Query 的 QueryClient 在此層提供，確保全域資料快取共享
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { SubscriptionListPage } from './pages/SubscriptionListPage';
import { AddSubscriptionPage } from './pages/AddSubscriptionPage';
import { EditSubscriptionPage } from './pages/EditSubscriptionPage';
import { HistoryPage } from './pages/HistoryPage';
import { getToken } from './utils/storage';

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

          {/* 受保護路由：需要登入才能訪問 */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout>
                  <SubscriptionListPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subscriptions/add"
            element={
              <ProtectedRoute>
                <Layout>
                  <AddSubscriptionPage />
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

          {/* 未知路徑重導至首頁 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
