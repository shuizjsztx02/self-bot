@echo off
chcp 65001 >nul
title A股实时行情数据获取工具 - 快速启动

echo ==========================================
echo   A股实时行情数据获取工具 - 快速启动
echo ==========================================
echo.

REM 检查Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ 未找到Python，请先安装Python
    pause
    exit /b 1
)

python --version
if %errorlevel% neq 0 (
    echo ❌ Python版本检查失败
    pause
    exit /b 1
)

echo ✅ Python已安装

REM 检查pip
where pip >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ 未找到pip，请先安装pip
    pause
    exit /b 1
)

echo ✅ pip已安装

REM 创建虚拟环境（可选）
set /p create_venv="是否创建虚拟环境？(y/n): "
if /i "%create_venv%"=="y" (
    echo 创建虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo ✅ 虚拟环境已激活
)

REM 安装依赖
echo.
echo 安装依赖...
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo ✅ 依赖安装成功
) else (
    echo ❌ 依赖安装失败，尝试使用国内镜像...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

REM 测试AKShare
echo.
echo 测试AKShare安装...
python simple_akshare_test.py

if %errorlevel% equ 0 (
    echo ✅ AKShare测试成功
) else (
    echo ❌ AKShare测试失败
    pause
    exit /b 1
)

:menu
echo.
echo ==========================================
echo   请选择要执行的操作：
echo ==========================================
echo 1. 获取实时行情数据
echo 2. 启动定时数据收集
echo 3. 查看配置
echo 4. 测试所有功能
echo 5. 退出
echo ==========================================

set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" (
    echo 执行实时数据获取...
    python get_a_share_realtime_data.py
    goto :end
)

if "%choice%"=="2" (
    echo 启动定时数据收集...
    python schedule_data_collection.py
    goto :end
)

if "%choice%"=="3" (
    echo 查看配置...
    python config_realtime.py
    goto :end
)

if "%choice%"=="4" (
    echo 测试所有功能...
    echo 1. 测试AKShare...
    python simple_akshare_test.py
    echo.
    echo 2. 测试实时数据获取...
    python get_a_share_realtime_data.py
    echo.
    echo 3. 查看配置...
    python config_realtime.py
    goto :end
)

if "%choice%"=="5" (
    echo 退出程序
    goto :exit
)

echo 无效选项
goto :menu

:end
echo.
echo ==========================================
echo   程序执行完成
echo ==========================================

REM 如果使用了虚拟环境，询问是否退出
if /i "%create_venv%"=="y" (
    set /p exit_venv="是否退出虚拟环境？(y/n): "
    if /i "%exit_venv%"=="y" (
        deactivate
        echo ✅ 已退出虚拟环境
    )
)

:exit
pause