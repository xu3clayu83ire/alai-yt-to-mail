# Python 環境：py vs python、虛擬環境與 uv

## 為何要用 `py` 而不是 `python`？

Windows 安裝 Python 時，預設提供的指令是 `py`（Python Launcher for Windows），而不是 `python`。

| 指令 | 說明 |
|------|------|
| `py` | Windows 專屬啟動器，自動找到系統安裝的 Python |
| `python` | Linux/Mac 習慣用法，Windows 上不一定存在 |
| `python3` | Linux 用來區分 Python 2/3，Windows 通常也不存在 |

在 Windows 上，永遠用 `py` 取代 `python`。

---

## 什麼是虛擬環境？

Python 套件預設安裝在「全域」，所有專案共用同一份套件。這會造成問題：

- 專案 A 需要 `requests==2.28`，專案 B 需要 `requests==2.31` → 衝突
- 升級某個套件可能導致其他專案壞掉

**虛擬環境（venv）** 是一個獨立的資料夾（通常叫 `.venv`），裡面有專屬的 Python 與套件，跟全域完全隔離。每個專案一個虛擬環境，互不干擾。

---

## 使用 uv 管理虛擬環境

[uv](https://docs.astral.sh/uv/) 是現代 Python 套件管理工具，比傳統 `pip` + `venv` 快很多。

### 建立虛擬環境

```powershell
uv venv
```

在當前目錄產生 `.venv` 資料夾。

### 安裝套件

```powershell
uv pip install -r requirements.txt
```

套件只裝在 `.venv` 裡，不影響全域。

### 執行腳本（不需手動啟動環境）

```powershell
uv run py script.py
```

`uv run` 自動使用 `.venv` 裡的環境執行，**不需要手動啟動虛擬環境**，這是最方便的方式。

### 手動啟動虛擬環境（非必要）

若需要在 shell 裡持續使用虛擬環境（例如連續執行多個指令）：

```powershell
.venv\Scripts\Activate.ps1
```

啟動後 shell 前面會出現 `(.venv)` 提示，此時直接用 `py` 執行腳本即可。

---

## 本專案的建議做法

```powershell
# 只需做一次：建立虛擬環境並安裝套件
cd yt-to-mail\scheduler
uv venv
uv pip install -r requirements.txt

# 之後每次執行：
uv run py run.py
uv run py test_run.py
```
