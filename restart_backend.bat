@echo off
chcp 65001 >nul
echo ========================================
echo 正在重启后端服务...
echo ========================================

REM 切换到项目目录
cd /d "%~dp0"

REM 停止现有的 Python 进程（监听 8000 端口的）
echo.
echo [1/3] 正在停止现有后端服务...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo 发现进程 ID: %%a，正在停止...
    taskkill /F /PID %%a >nul 2>&1
)

REM 等待进程完全停止
timeout /t 2 /nobreak >nul

REM 检查是否还有 Python 进程在运行（可选，更激进的方式）
REM echo [可选] 停止所有 Python 进程...
REM taskkill /F /IM python.exe >nul 2>&1
REM timeout /t 1 /nobreak >nul

REM 启动新的后端服务
echo.
echo [2/3] 正在启动新的后端服务...
echo 服务将在后台运行，请查看新的命令行窗口...
echo.

REM 在新窗口中启动服务，这样可以看到日志输出
start "Cognee Backend Server" cmd /k "cd /d %~dp0 && uv run python -m cognee.api.client"

REM 等待服务启动
echo [3/3] 等待服务启动...
timeout /t 8 /nobreak >nul

REM 检查服务是否成功启动
echo.
echo 正在检查服务状态...
timeout /t 2 /nobreak >nul

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% == 0 (
    echo.
    echo ========================================
    echo ✓ 后端服务已成功启动！
    echo ========================================
    echo 服务地址: http://localhost:8000
    echo 健康检查: http://localhost:8000/health
    echo.
    echo 提示: 服务在新窗口中运行，请不要关闭该窗口
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ✗ 后端服务可能未成功启动
    echo ========================================
    echo 请检查新打开的命令行窗口中的错误信息
    echo ========================================
)

echo.
pause

