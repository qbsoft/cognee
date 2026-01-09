@echo off
chcp 65001 >nul
echo ========================================
echo 正在重启前端服务...
echo ========================================

REM 切换到项目根目录
cd /d "%~dp0"

REM 切换到前端目录
if not exist "cognee-frontend" (
    echo 错误: 找不到 cognee-frontend 目录
    echo 请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

cd cognee-frontend

REM 停止现有的 Node.js 进程（监听 3000 端口的）
echo.
echo [1/3] 正在停止现有前端服务...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    echo 发现进程 ID: %%a，正在停止...
    taskkill /F /PID %%a >nul 2>&1
)

REM 等待进程完全停止
timeout /t 2 /nobreak >nul

REM 启动新的前端服务
echo.
echo [2/3] 正在启动新的前端服务...
echo 服务将在新窗口中运行，请查看新的命令行窗口...
echo.

REM 在新窗口中启动服务，这样可以看到日志输出
start "Cognee Frontend Server" cmd /k "cd /d %~dp0cognee-frontend && npm run dev"

REM 等待服务启动
echo [3/3] 等待服务启动...
timeout /t 10 /nobreak >nul

REM 检查服务是否成功启动
echo.
echo 正在检查服务状态...
timeout /t 2 /nobreak >nul

netstat -ano | findstr ":3000" | findstr "LISTENING" >nul
if %errorlevel% == 0 (
    echo.
    echo ========================================
    echo ✓ 前端服务已成功启动！
    echo ========================================
    echo 服务地址: http://localhost:3000
    echo.
    echo 提示: 服务在新窗口中运行，请不要关闭该窗口
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ✗ 前端服务可能未成功启动
    echo ========================================
    echo 请检查新打开的命令行窗口中的错误信息
    echo 如果首次运行，可能需要先执行: npm install
    echo ========================================
)

echo.
pause

