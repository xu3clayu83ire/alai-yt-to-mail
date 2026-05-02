/**
 * 時區轉換工具函式
 * 後端 API 儲存與回傳的時間均為 UTC，前端需轉換為瀏覽器本地時區顯示
 * 送出 API 前需將本地時間換算回 UTC，避免用戶混淆
 */

/**
 * 將 UTC HH:MM 時間字串轉換為瀏覽器本地時間 HH:MM
 * 利用 Date 物件進行換算，正確處理跨日與夏令時情況
 * 例：UTC 14:00 → 台灣時間 22:00
 */
export function utcTimeToLocal(utcTime: string): string {
  const [hoursStr, minutesStr] = utcTime.split(':');
  const hours = parseInt(hoursStr, 10);
  const minutes = parseInt(minutesStr, 10);

  // 使用當天日期建立 UTC 時間點，再取得本地時間
  const now = new Date();
  const utcDate = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hours, minutes, 0)
  );

  const localHours = utcDate.getHours();
  const localMinutes = utcDate.getMinutes();

  return `${String(localHours).padStart(2, '0')}:${String(localMinutes).padStart(2, '0')}`;
}

/**
 * 將瀏覽器本地時間 HH:MM 換算為 UTC HH:MM
 * 為 utcTimeToLocal 的反向操作，確保資料送出前完成時區還原
 * 例：台灣時間 22:00 → UTC 14:00
 */
export function localTimeToUtc(localTime: string): string {
  const [hoursStr, minutesStr] = localTime.split(':');
  const hours = parseInt(hoursStr, 10);
  const minutes = parseInt(minutesStr, 10);

  // 使用當天日期建立本地時間點，再取得 UTC 時間
  const now = new Date();
  const localDate = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    hours,
    minutes,
    0
  );

  const utcHours = localDate.getUTCHours();
  const utcMinutes = localDate.getUTCMinutes();

  return `${String(utcHours).padStart(2, '0')}:${String(utcMinutes).padStart(2, '0')}`;
}

/**
 * 將 ISO 8601 UTC 時間戳記轉換為本地可讀格式
 * 統一顯示格式為 YYYY/MM/DD HH:MM，便於用戶閱讀
 * 例："2026-05-01T14:00:00Z" → "2026/05/01 22:00"
 */
export function formatUtcTimestamp(utcTimestamp: string): string {
  const date = new Date(utcTimestamp);

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');

  return `${year}/${month}/${day} ${hours}:${minutes}`;
}
