"""
yt-to-mail 排程器管理工具。

提供互動式選單，讓使用者控制 Windows 工作排程器：
- 查看目前狀態（啟用/停用、執行間隔）
- 啟用或停用排程
- 變更執行間隔（分鐘）
"""

import subprocess
import sys


TASK_NAME = "yt-to-mail-scheduler"
VBS_PATH = r"D:\12_Claude_Assistant\yt-to-mail\scheduler\run_silent.vbs"
WORK_DIR = r"D:\12_Claude_Assistant\yt-to-mail\scheduler"


def run_ps(command: str) -> tuple[int, str]:
    """執行 PowerShell 指令並回傳 (exit_code, output)。"""
    result = subprocess.run(
        ["powershell", "-NonInteractive", "-Command", command],
        capture_output=True, text=True
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def get_status() -> dict:
    """取得排程工作目前的狀態資訊。"""
    code, out = run_ps(
        f'Get-ScheduledTask -TaskName "{TASK_NAME}" -ErrorAction SilentlyContinue '
        f'| Select-Object State | ConvertTo-Json'
    )
    if code != 0 or not out:
        return {"exists": False}

    code2, out2 = run_ps(
        f'Get-ScheduledTaskInfo -TaskName "{TASK_NAME}" '
        f'| Select-Object LastRunTime, LastTaskResult, NextRunTime | ConvertTo-Json'
    )
    code3, interval_out = run_ps(
        f'(Get-ScheduledTask -TaskName "{TASK_NAME}").Triggers[0].Repetition.Interval'
    )

    import json
    state_data = json.loads(out) if out.startswith("{") else {}
    info_data = json.loads(out2) if out2.startswith("{") else {}

    return {
        "exists": True,
        "state": state_data.get("State", "Unknown"),
        "last_run": info_data.get("LastRunTime", "N/A"),
        "last_result": info_data.get("LastTaskResult", "N/A"),
        "next_run": info_data.get("NextRunTime", "N/A"),
        "interval": interval_out.strip(),
    }


def show_status():
    """顯示排程工作的目前狀態。"""
    status = get_status()
    print("\n=== yt-to-mail 排程器狀態 ===")
    if not status["exists"]:
        print("❌ 排程工作不存在（尚未建立）")
        return

    state_label = "✅ 執行中" if status["state"] == "Ready" else "⏸ 已停用" if status["state"] == "Disabled" else status["state"]
    print(f"狀態：{state_label}")
    print(f"執行間隔：{status['interval']}")
    print(f"上次執行：{status['last_run']}")
    print(f"上次結果：{'成功 (0)' if status['last_result'] == 0 else status['last_result']}")
    print(f"下次執行：{status['next_run']}")


def enable_task():
    """啟用排程工作。"""
    code, out = run_ps(f'Enable-ScheduledTask -TaskName "{TASK_NAME}" 2>&1 | Out-Null; echo "ok"')
    if "ok" in out:
        print("✅ 排程已啟用")
    else:
        print(f"❌ 啟用失敗：{out}")


def disable_task():
    """停用排程工作（不刪除）。"""
    code, out = run_ps(f'Disable-ScheduledTask -TaskName "{TASK_NAME}" 2>&1 | Out-Null; echo "ok"')
    if "ok" in out:
        print("⏸ 排程已停用")
    else:
        print(f"❌ 停用失敗：{out}")


def set_interval(minutes: int):
    """重新建立排程工作並設定指定的執行間隔（分鐘）。"""
    ps_script = f"""
$action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument '"{VBS_PATH}"' `
    -WorkingDirectory "{WORK_DIR}"

$trigger = New-ScheduledTaskTrigger `
    -RepetitionInterval (New-TimeSpan -Minutes {minutes}) `
    -Once `
    -At (Get-Date)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "{TASK_NAME}" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "yt-to-mail local scheduler" `
    -RunLevel Highest `
    -Force | Out-Null
echo "ok"
"""
    code, out = run_ps(ps_script)
    if "ok" in out:
        print(f"✅ 排程已更新，每 {minutes} 分鐘執行一次")
    else:
        print(f"❌ 更新失敗（需要管理員權限）：{out}")


def main():
    """主選單互動迴圈。"""
    print("yt-to-mail 排程器管理工具")

    while True:
        show_status()
        print("\n選項：")
        print("  1. 啟用排程")
        print("  2. 停用排程")
        print("  3. 變更執行間隔（分鐘）")
        print("  0. 離開")
        choice = input("\n請輸入選項：").strip()

        if choice == "1":
            enable_task()
        elif choice == "2":
            disable_task()
        elif choice == "3":
            try:
                minutes = int(input("執行間隔（分鐘，1~60）：").strip())
                if 1 <= minutes <= 60:
                    set_interval(minutes)
                else:
                    print("請輸入 1 到 60 之間的數字")
            except ValueError:
                print("請輸入有效的數字")
        elif choice == "0":
            print("離開")
            sys.exit(0)
        else:
            print("無效選項")


if __name__ == "__main__":
    main()
