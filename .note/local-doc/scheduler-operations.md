# yt-to-mail 排程器操作指南

## 管理排程器（manage.py）

### 啟動管理工具

在 `scheduler/` 目錄執行：

```powershell
cd D:\12_Claude_Assistant\yt-to-mail\scheduler
uv run python manage.py
```

### 選單說明

```
=== yt-to-mail 排程器狀態 ===
狀態：✅ 執行中
執行間隔：PT1M
上次執行：2026/5/2 下午 06:57:46
上次結果：成功 (0)
下次執行：2026/5/2 下午 06:58:46

選項：
  1. 啟用排程
  2. 停用排程
  3. 變更執行間隔（分鐘）
  0. 離開
```

| 選項 | 說明 |
|------|------|
| 1 | 啟用已停用的排程（電腦重開機後若停用可用此重啟） |
| 2 | 暫停排程，不刪除設定，之後可再啟用 |
| 3 | 變更執行頻率，輸入 1～60 的整數（分鐘） |
| 0 | 離開管理工具 |

> **注意**：變更執行間隔需要管理員權限，請用「以系統管理員身份執行」開啟終端機後再執行 `manage.py`。

---

## 監看排程運作

### 方式一：即時監看 log（推薦）

```powershell
Get-Content "D:\12_Claude_Assistant\yt-to-mail\scheduler\logs\scheduler.log" -Tail 10 -Wait
```

`-Wait` 會持續監看，每次排程觸發都會即時顯示新行，按 `Ctrl+C` 停止。

**正常執行範例（無到期訂閱）：**
```
[2026-05-02 18:57:48 UTC] INFO [__main__] 開始執行，當前 UTC 時間：10:57
[2026-05-02 18:57:48 UTC] INFO [dynamo_reader] 查詢 UTC 時間 10:57 的到期訂閱
[2026-05-02 18:57:49 UTC] INFO [dynamo_reader] 查詢到 0 個到期訂閱
[2026-05-02 18:57:49 UTC] INFO [__main__] 無到期訂閱，執行完成，耗時 0.9 秒
```

**有訂閱到期時的範例：**
```
[2026-05-02 14:00:01 UTC] INFO [__main__] 開始執行，當前 UTC 時間：14:00
[2026-05-02 14:00:01 UTC] INFO [dynamo_reader] 查詢到 2 個到期訂閱
[2026-05-02 14:00:05 UTC] INFO [processor] [sub:uuid-1] 處理中 - 頻道: @channel1
[2026-05-02 14:00:45 UTC] INFO [processor] [sub:uuid-1] 完成 - video_id: abc123, status: done
[2026-05-02 14:01:10 UTC] INFO [__main__] 執行完成，耗時 69 秒
```

### 方式二：查看 log 歷史

```powershell
# 查看今日完整 log
Get-Content "D:\12_Claude_Assistant\yt-to-mail\scheduler\logs\scheduler.log"

# 查看歸檔 log（格式：scheduler.log.2026-05-01）
Get-ChildItem "D:\12_Claude_Assistant\yt-to-mail\scheduler\logs\"
```

> Log 每日自動 rotate，保留 7 天，超過自動刪除。

### 方式三：Windows 工作排程器 UI

1. 按 `Win + S` 搜尋「工作排程器」
2. 左側展開「工作排程器程式庫」
3. 找到 `yt-to-mail-scheduler`
4. 右側可看到上次執行時間與結果代碼（0 = 成功）

---

## 常見狀態碼

| LastTaskResult | 意義 |
|----------------|------|
| 0 | 執行成功 |
| 1 | 執行失敗（查 log 確認原因） |
| 267009 | 排程正在執行中 |
| 267011 | 排程尚未執行過 |

---

## 靜默執行說明

排程器透過 `run_silent.vbs` 啟動，不會顯示任何視窗。  
所有執行結果均寫入 `logs/scheduler.log`，這是確認運作狀態的唯一管道。
