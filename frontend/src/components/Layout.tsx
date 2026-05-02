/**
 * 共用版面元件
 * 提供一致的頁首、導覽列與主要內容區域
 * 所有需要登入的頁面都透過此元件包裝，確保一致的 UI 體驗
 */

import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

interface LayoutProps {
  children: React.ReactNode;
}

/**
 * 主要版面框架，包含 Header 與導覽連結
 * Header 右側顯示登出按鈕，點擊後清除 token 並重導至登入頁
 */
export function Layout({ children }: LayoutProps) {
  const { logout } = useAuth();
  const location = useLocation();

  /** 判斷導覽連結是否為當前路徑，用於高亮顯示 */
  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 頁首導覽列 */}
      <header className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          {/* 應用名稱 */}
          <Link to="/" className="text-xl font-bold text-red-600 hover:text-red-700">
            DailyCast
          </Link>

          {/* 導覽連結 */}
          <nav className="flex items-center gap-4">
            <Link
              to="/"
              className={`text-sm font-medium transition-colors ${
                isActive('/') ? 'text-red-600' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              我的訂閱
            </Link>
            <Link
              to="/history"
              className={`text-sm font-medium transition-colors ${
                isActive('/history') ? 'text-red-600' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              歷史紀錄
            </Link>
            <button
              onClick={logout}
              className="text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors"
            >
              登出
            </button>
          </nav>
        </div>
      </header>

      {/* 主要內容區域 */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}
