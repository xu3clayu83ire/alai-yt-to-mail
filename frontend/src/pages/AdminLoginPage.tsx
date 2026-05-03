/**
 * 管理員登入頁面
 * 使用現有 POST /auth/login 端點，以 admin email 登入取得含 is_admin 的 JWT
 * admin token 存入獨立的 localStorage key（admin_access_token），與一般用戶 token 分開
 * 登入成功後跳轉至 /admin/subscriptions，失敗（401）顯示友善錯誤訊息
 * 此頁面不使用 Layout.tsx，採用獨立簡潔的管理後台風格
 */

import { useState } from 'react';
import type { ReactElement } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { login } from '../api/auth';
import { setAdminToken } from '../utils/storage';

/** 管理員登入表單驗證 Schema */
const adminLoginSchema = z.object({
  email: z.string().email('請輸入有效的 Email 格式'),
  password: z.string().min(1, '請輸入密碼'),
});

type AdminLoginFormData = z.infer<typeof adminLoginSchema>;

/**
 * 管理員登入頁面元件
 * 登入失敗（401）時顯示「Email 或密碼錯誤」，不透露是否為管理員帳號
 */
export function AdminLoginPage(): ReactElement {
  const navigate = useNavigate();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AdminLoginFormData>({
    resolver: zodResolver(adminLoginSchema),
  });

  /**
   * 處理管理員登入表單提交
   * 呼叫現有 /auth/login 端點；後端依 email 判斷是否為 admin 並在 JWT 內加入 is_admin
   * 成功後將 token 存入 admin_access_token key，跳轉至管理後台
   */
  const onSubmit = async (data: AdminLoginFormData): Promise<void> => {
    setApiError(null);
    try {
      const response = await login(data);
      setAdminToken(response.access_token);
      navigate('/admin/subscriptions');
    } catch (error: unknown) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        setApiError('Email 或密碼錯誤');
      } else {
        setApiError('登入失敗，請稍後再試');
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-md p-8 w-full max-w-md">
        {/* 頁面標題 */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">管理員登入</h1>
          <p className="text-gray-500 text-sm mt-1">DailyCast 後台管理系統</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {/* Email 欄位 */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              {...register('email')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="admin@example.com"
              autoComplete="email"
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
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
              autoComplete="current-password"
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
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? '登入中...' : '登入'}
          </button>
        </form>
      </div>
    </div>
  );
}
