/**
 * 認證相關 API 呼叫函式
 * 封裝登入與註冊端點，統一錯誤處理介面
 */

import apiClient from './client';
import type { LoginRequest, RegisterRequest, LoginResponse, UserResponse } from '../types';

/**
 * 呼叫後端登入 API，取得 JWT access token
 * 登入成功後需由呼叫端將 token 存入 localStorage
 */
export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login', data);
  return response.data;
}

/**
 * 呼叫後端註冊 API，建立新用戶帳號
 * 註冊成功後需再呼叫 login 取得 token 以完成自動登入流程
 */
export async function register(data: RegisterRequest): Promise<UserResponse> {
  const response = await apiClient.post<UserResponse>('/auth/register', data);
  return response.data;
}
