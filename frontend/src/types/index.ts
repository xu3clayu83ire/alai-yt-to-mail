/**
 * 全域 TypeScript 型別定義
 * 集中管理所有 API 請求/回應介面，確保型別安全與可維護性
 */

// ===================== 用戶認證相關 =====================

/** 登入請求 payload */
export interface LoginRequest {
  email: string;
  password: string;
}

/** 註冊請求 payload */
export interface RegisterRequest {
  email: string;
  password: string;
}

/** 登入成功回應（含 JWT）*/
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/** 用戶資訊回應 */
export interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}

// ===================== 訂閱相關 =====================

/** 訂閱項目（API 回傳格式，send_time 為 UTC HH:MM）*/
export interface Subscription {
  id: string;
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
  is_active: boolean;
  created_at: string;
}

/** 新增訂閱請求（send_time 需在送出前換算為 UTC）*/
export interface SubscriptionCreateRequest {
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
}

/** 編輯訂閱請求（所有欄位為選填）*/
export interface SubscriptionUpdateRequest {
  recipient_email?: string;
  audio_speed?: number;
  send_time?: string;
  is_active?: boolean;
}

// ===================== 歷史紀錄相關 =====================

/** 歷史紀錄狀態類型 */
export type HistoryStatus = 'done' | 'failed' | 'skipped_language';

/** 歷史紀錄項目（sent_at 為 ISO 8601 UTC 格式）*/
export interface HistoryItem {
  id: string;
  subscription_id: string;
  video_id: string;
  video_title: string;
  sent_at: string;
  status: HistoryStatus;
  error_message?: string;
}

// ===================== 頻道管理相關 =====================

/** 公開頻道列表項目（無需認證即可取得）*/
export interface PublicChannelItem {
  channel_id: string;
  channel_name: string;
  channel_url: string;
}

/** 管理員頻道項目（含建立時間）*/
export interface ChannelItem {
  channel_id: string;
  channel_name: string;
  channel_url: string;
  created_at: string;
}

/** 建立頻道請求 payload */
export interface ChannelCreateRequest {
  channel_id: string;
  channel_name: string;
  channel_url: string;
}

/** 更新頻道請求 payload（所有欄位選填）*/
export interface ChannelUpdateRequest {
  channel_name?: string;
  channel_url?: string;
}

/** 刪除頻道回應（含受影響訂閱數）*/
export interface ChannelDeleteResponse {
  message: string;
  cancelled_subscriptions: number;
}

// ===================== API 錯誤 =====================

/** API 錯誤回應格式 */
export interface ApiError {
  detail: string;
}

// ===================== 管理員後台相關 =====================

/**
 * 管理員後台訂閱項目型別
 * 包含 user_id 欄位（即訂閱者 email），供管理員識別各筆訂閱所屬用戶
 */
export interface AdminSubscriptionItem {
  id: string;
  user_id: string;
  channel_url: string;
  channel_id: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
  is_active: boolean;
  auto_cancel_days: number;
  no_new_video_days: number;
  created_at: string;
}

// ===================== 公開 API 相關 =====================

/** 公開訂閱請求（無需 JWT，send_time 需為 UTC HH:MM）*/
export interface PublicSubscribeRequest {
  recipient_email: string;
  channel_url: string;
  audio_speed: number;
  send_time: string;
  auto_cancel_days: number;
}

/** 公開訂閱項目（含自動取消設定與無新影片天數）*/
export interface PublicSubscriptionItem {
  id: string;
  channel_url: string;
  channel_name: string;
  recipient_email: string;
  audio_speed: number;
  send_time: string;
  is_active: boolean;
  auto_cancel_days: number;
  no_new_video_days: number;
  created_at: string;
}
