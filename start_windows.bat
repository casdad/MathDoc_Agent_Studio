@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================
echo       MathDoc Agent Studio
echo ====================================

rem 查找 Python：PATH 中的 python 优先，其次 py 启动器
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  echo [错误] 未发现 Python。请先安装 Python 3.10 或以上版本：
  echo        https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (
  rem python 可能是 Microsoft Store 占位符，退回 py 启动器再试一次
  where py >nul 2>nul && set "PY=py -3"
)
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [错误] Python 无法运行或版本低于 3.10，请重新安装 Python 3.10+。
  pause
  exit /b 1
)

rem Pandoc：PATH 中找不到时，尝试常见安装目录并临时补进 PATH 供 server.py 使用
where pandoc >nul 2>nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Pandoc\pandoc.exe" set "PATH=%LOCALAPPDATA%\Pandoc;%PATH%"
  if exist "%ProgramFiles%\Pandoc\pandoc.exe" set "PATH=%ProgramFiles%\Pandoc;%PATH%"
)
where pandoc >nul 2>nul
if errorlevel 1 (
  echo [错误] 未发现 Pandoc。请先运行：winget install --id JohnMacFarlane.Pandoc -e
  echo 安装完成后请重新打开此程序。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [信息] 第一次启动：正在创建虚拟环境...
  %PY% -m venv .venv
  if errorlevel 1 goto failure
)
rem 依赖已可用时跳过联网，避免每次启动都访问软件源
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, httpx, bleach, pydantic" >nul 2>nul
if errorlevel 1 (
  echo [信息] 正在安装 Python 依赖，请稍候...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --timeout 20 --retries 1 -r requirements.txt
  if errorlevel 1 (
    echo [提示] 默认软件源安装失败，改用官方 PyPI 重试...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --timeout 20 --retries 1 --index-url https://pypi.org/simple -r requirements.txt
  )
  if errorlevel 1 goto failure
)
if not exist "templates\reference.docx" (
  echo [提示] 未检测到 Word 样式模板，将使用 Pandoc 默认模板。
)
echo.
echo [就绪] 启动本地服务，准备打开浏览器...
".venv\Scripts\python.exe" launch.py
if errorlevel 1 goto failure
exit /b 0

:failure
echo.
echo [失败] 安装或初始化失败，请检查上方错误信息、网络、Python 环境和权限。
pause
exit /b 1
