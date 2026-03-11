@echo off
chcp 65001 >nul
echo ==========================================
echo AKShare A股实时行情数据获取工具
echo ==========================================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到pip，请先安装pip
    pause
    exit /b 1
)

REM 创建虚拟环境（可选）
if not exist "venv" (
    echo 📦 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo 🔧 激活虚拟环境...
    call venv\Scripts\activate.bat
)

REM 安装依赖
echo 📥 安装依赖包...
pip install -r requirements.txt

REM 创建数据目录
if not exist "realtime_data" mkdir realtime_data

echo.
echo 请选择要运行的程序：
echo 1. 测试AKShare安装
echo 2. 获取实时行情数据（单次）
echo 3. 定时获取实时数据
echo 4. 查看使用说明
echo 5. 退出
echo.

set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" (
    echo 运行测试脚本...
    python test_akshare_realtime.py
) else if "%choice%"=="2" (
    echo 获取实时行情数据...
    python get_a_share_realtime_data.py
) else if "%choice%"=="3" (
    echo 启动定时数据收集...
    echo 按 Ctrl+C 停止程序
    python schedule_realtime_data.py
) else if "%choice%"=="4" (
    echo 查看使用说明...
    type README.md | head -50
    echo.
    echo 完整说明请查看 README.md 文件
) else if "%choice%"=="5" (
    echo 退出程序
    exit /b 0
) else (
    echo 无效选项
)

echo.
echo ==========================================
echo 程序执行完成
echo ==========================================
pause