/**
 * 註冊頁面
 * 提供 Email/Password/Confirm Password 表單，註冊成功後自動登入並重導首頁
 * 確認密碼欄位使用 Zod superRefine 驗證一致性
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { register as registerApi, login } from '../api/auth';
import { setToken } from '../utils/storage';

/** 註冊表單驗證 Schema，包含確認密碼一致性檢查 */
const registerSchema = z
  .object({
    email: z.string().email('請輸入有效的 Email 格式'),
    password: z.string().min(8, '密碼至少 8 個字元'),
    confirmPassword: z.string().min(1, '請確認密碼'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: '兩次密碼輸入不一致',
    path: ['confirmPassword'],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

/**
 * 註冊頁面元件
 * 註冊成功後自動以同帳密呼叫登入 API，取得 token 後重導首頁
 * Email 重複（409）時顯示友善錯誤提示
 */
export function RegisterPage() {
  const navigate = useNavigate();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  /**
   * 處理註冊表單提交
   * 成功後自動登入，取得 token 存入 localStorage 並重導首頁
   */
  const onSubmit = async (data: RegisterFormData) => {
    setApiError(null);
    try {
      await registerApi({ email: data.email, password: data.password });
      // 註冊成功後自動登入
      const loginResponse = await login({ email: data.email, password: data.password });
      setToken(loginResponse.access_token);
      navigate('/');
    } catch (error: unknown) {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setApiError('此 Email 已被使用');
      } else {
        setApiError('註冊失敗，請稍後再試');
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
          <p className="text-gray-500 mt-1">建立新帳號</p>
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
              placeholder="至少 8 個字元"
            />
            {errors.password && (
              <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>
            )}
          </div>

          {/* Confirm Password 欄位 */}
          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              確認密碼
            </label>
            <input
              id="confirmPassword"
              type="password"
              {...register('confirmPassword')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="再次輸入密碼"
            />
            {errors.confirmPassword && (
              <p className="text-red-500 text-xs mt-1">{errors.confirmPassword.message}</p>
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
            {isSubmitting ? '註冊中...' : '註冊'}
          </button>
        </form>

        {/* 前往登入連結 */}
        <p className="text-center text-sm text-gray-500 mt-4">
          已有帳號？{' '}
          <Link to="/login" className="text-red-600 hover:text-red-700 font-medium">
            前往登入
          </Link>
        </p>
      </div>
    </div>
  );
}
