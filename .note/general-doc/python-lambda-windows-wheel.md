# Windows 開發環境建置 Lambda Python 套件的 wheel 相容問題

**日期**：2026-05-02
**類型**：問題排除 / 設定步驟

---

## 發生了什麼

在 Windows 環境執行 `pip install` 將 Python 套件打包進 Lambda Layer 或部署包時，pip 會自動下載針對 Windows 平台編譯的 `.whl` 檔案。這些 wheel 檔案與 AWS Lambda 的執行環境（Amazon Linux 2 / x86_64 或 arm64）二進位格式不相容，導致 Lambda 函式執行時出現類似以下錯誤：

```
[ERROR] Runtime.ImportModuleError: Unable to import module 'app': No module named 'pydantic_core._pydantic_core'
```

或：

```
OSError: /var/task/cryptography/hazmat/bindings/_rust.abi3.so: cannot open shared object file: No such file or directory
```

## 根本原因

含有 C extension 或 Rust extension 的 Python 套件，在 `pip install` 時會根據當前作業系統與 CPU 架構選擇對應的預編譯 wheel。Windows 上安裝的是 `win_amd64` 版本的 `.so`/`.pyd` 檔案，但 Lambda 需要的是針對 `manylinux` 編譯的 `.so` 檔案。兩者的共用函式庫（glibc 等）與二進位格式（ELF vs PE）根本不同，無法在 Linux 上載入。

**受影響套件**（本專案 yt-to-mail 使用的 C extension）：

| 套件 | 為何使用 | C extension 原因 |
|------|---------|----------------|
| `pydantic[email]` | FastAPI 請求/回應資料驗證，`[email]` extra 提供 `EmailStr` 型別驗證 email 格式 | `pydantic-core` 底層用 Rust 編譯 |
| `python-jose[cryptography]` | 產生與驗證 JWT token（登入後發給前端的身份憑證），`[cryptography]` 提供 HS256 簽名算法 | `cryptography` 套件含 Rust/C 編譯碼 |
| `bcrypt` | 用戶密碼雜湊儲存（不能存明文），登入時比對密碼雜湊 | bcrypt 雜湊演算法是 C extension |

身份驗證流程對應：
- 用戶**註冊** → `bcrypt` 把密碼雜湊後存進 DynamoDB
- 用戶**登入** → `bcrypt` 比對密碼，`python-jose` 發 JWT
- API **收到請求** → `pydantic` 驗證傳入的 JSON 格式（包括 email 格式）

## 解法

在 `pip install` 時明確指定目標平台，強制下載 Linux 相容的 wheel：

```powershell
pip install `
  --platform manylinux2014_x86_64 `
  --implementation cp `
  --python-version 3.12 `
  --only-binary=:all: `
  --target ./layer/python `
  pydantic[email] python-jose[cryptography] bcrypt
```

若套件不提供對應平台的預編譯 wheel，`--only-binary=:all:` 會導致安裝失敗。此時需改用 Docker（Amazon Linux 2 映像）在容器內執行 `pip install`，確保編譯環境與 Lambda 一致：

```powershell
docker run --rm -v "${PWD}/layer:/out" public.ecr.aws/lambda/python:3.12 `
  pip install pydantic[email] python-jose[cryptography] bcrypt -t /out/python
```

## 風險與注意事項

- `--platform manylinux2014_x86_64` 只適用於 x86_64 架構的 Lambda；若使用 arm64（Graviton），需改為 `manylinux2014_aarch64`。
- `--only-binary=:all:` 若遇到沒有預編譯 wheel 的套件會直接報錯，必須改用 Docker 方式。
- Python 版本（`--python-version`）需與 Lambda Runtime 版本完全一致，否則 ABI 可能不相容。
- 此方式在 Windows 上無法驗證套件是否真的能正確 import，只能部署後才能確認。

## 結論

**只要 Lambda 依賴中有任何 C extension（`.whl` 二進位套件），在 Windows 上就必須用 Docker 打包。**

### 判斷原則

| 依賴類型 | 範例 | Windows 本機 pip 是否可行 |
|---------|------|--------------------------|
| Pure Python | `requests`, `boto3`, `fastapi`, `mangum` | ✅ 可以，跨平台 |
| C extension | `pydantic`, `bcrypt`, `cryptography`, `numpy`, `pandas`, `pillow` | ❌ 不行，wheel 平台鎖定 |

**判斷方式**：在 PyPI 套件頁面查看「Download files」，若有 `*-win_amd64.whl` 等平台專屬檔案，即為 C extension；若只有 `*-py3-none-any.whl`，則為 Pure Python。

## 參考資料

- [pip install --platform 官方文件](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-platform)
- [AWS Lambda：使用 Python 套件含 C extension](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-native-libraries)
- [manylinux wheel 標準（PEP 600）](https://peps.python.org/pep-0600/)
