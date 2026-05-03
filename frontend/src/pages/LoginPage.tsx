/**
 * 登入頁面
 * 提供 Email/Password 表單，登入成功後將 JWT 存入 localStorage 並重導首頁
 * 使用 React Hook Form + Zod 確保表單驗證邏輯集中管理
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { login } from '../api/auth';
import { setToken, setAdminToken } from '../utils/storage';

/** 登入表單驗證 Schema */
const loginSchema = z.object({
  email: z.string().email('請輸入有效的 Email 格式'),
  password: z.string().min(8, '密碼至少 8 個字元'),
});

type LoginFormData = z.infer<typeof loginSchema>;

/**
 * 登入頁面元件
 * 登入失敗（401）時顯示友善錯誤訊息，避免透露過多系統資訊
 */
export function LoginPage() {
  const navigate = useNavigate();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  /**
   * 處理登入表單提交
   * 成功後將 token 存入 localStorage 並重導至首頁
   */
  const onSubmit = async (data: LoginFormData) => {
    setApiError(null);
    try {
      const response = await login(data);
      // 解碼 JWT payload 判斷是否為管理員，據此決定 token 儲存方式與跳轉目標
      let isAdmin = false;
      try {
        const payload = JSON.parse(atob(response.access_token.split('.')[1]));
        isAdmin = payload.is_admin === true;
      } catch {
        // JWT 格式異常時視為一般用戶，不影響正常登入流程
      }
      if (isAdmin) {
        setAdminToken(response.access_token);
        navigate('/admin/subscriptions');
      } else {
        setToken(response.access_token);
        navigate('/');
      }
    } catch (error: unknown) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        setApiError('Email 或密碼錯誤');
      } else {
        setApiError('登入失敗，請稍後再試');
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-md p-8 w-full max-w-md">
        {/* 原型聲明 Banner */}
        <div className="bg-amber-50 border-2 border-amber-400 rounded-lg px-4 py-3 mb-6 text-center">
          <p className="text-amber-800 font-bold text-sm">⚠️ 這是個人原型 Demo，非商業服務</p>
          <p className="text-amber-700 text-xs mt-1">此網站用於功能測試，不會蒐集或販售任何個人資料</p>
        </div>

        {/* 頁面標題 */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">DailyCast</h1>
          <p className="text-gray-500 mt-1">登入您的帳號</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Email 欄位 */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              {...register('email')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="your@email.com"
            />
            {errors.email && (
              <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>
            )}
          </div>

          {/* Password 欄位 */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              密碼
            </label>
            <input
              id="password"
              type="password"
              {...register('password')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="••••••••"
            />
            {errors.password && (
              <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>
            )}
          </div>

          {/* API 錯誤訊息 */}
          {apiError && (
            <div className="bg-red-50 border border-red-200 rounded-md px-3 py-2">
              <p className="text-red-600 text-sm">{apiError}</p>
            </div>
          )}

          {/* 提交按鈕 */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-red-600 text-white py-2 px-4 rounded-md font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? '登入中...' : '登入'}
          </button>
        </form>

        {/* 前往註冊連結 */}
        <p className="text-center text-sm text-gray-500 mt-4">
          還沒有帳號？{' '}
          <Link to="/register" className="text-red-600 hover:text-red-700 font-medium">
            立即註冊
          </Link>
        </p>
      </div>
    </div>
  );
}
