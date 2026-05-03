/**
 * localStorage JWT 存取工具
 * 集中管理 token 的讀寫與清除操作，避免 key 字串散落各處
 * 原型階段使用 localStorage，正式版需改為 HttpOnly Cookie
 * admin token 與一般用戶 token 使用不同 key，互不影響
 */

const TOKEN_KEY = 'access_token';
const ADMIN_TOKEN_KEY = 'admin_access_token';

/**
 * 從 localStorage 讀取 JWT token
 * 若未登入或 token 已被清除則回傳 null
 */
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * 將 JWT token 寫入 localStorage
 * 登入成功後呼叫，供後續 API 請求使用
 */
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * 清除 localStorage 中的 JWT token
 * 登出或收到 401 回應時呼叫，確保安全退出
 */
export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * 將管理員 JWT token 寫入 localStorage
 * 管理員登入成功後呼叫，與一般用戶 token 分開存放避免混淆
 */
export function setAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

/**
 * 從 localStorage 讀取管理員 JWT token
 * 若未登入或 token 已被清除則回傳 null
 */
export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

/**
 * 清除 localStorage 中的管理員 JWT token
 * 管理員登出或收到 401/403 回應時呼叫，確保安全退出
 */
export function removeAdminToken(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}
