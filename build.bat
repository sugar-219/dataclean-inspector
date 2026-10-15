@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "DC_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "DC_PYTHON=%~dp0.venv\Scripts\python.exe"
"%DC_PYTHON%" scripts\build_windows.py
if errorlevel 1 (
    echo 打包失败，请检查上方错误。
    exit /b 1
)
echo 打包完成：dist\数据清洗与质量检测工具\数据清洗与质量检测工具.exe
echo 请分发整个程序目录，保留 _internal 文件夹。
endlocal
