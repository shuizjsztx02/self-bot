#!/bin/bash

# AKShare A股实时行情数据获取工具 - 快速启动脚本

echo "=========================================="
echo "AKShare A股实时行情数据获取工具"
echo "=========================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ 未找到pip3，请先安装pip3"
    exit 1
fi

# 创建虚拟环境（可选）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    echo "🔧 激活虚拟环境..."
    source venv/bin/activate
fi

# 安装依赖
echo "📥 安装依赖包..."
pip install -r requirements.txt

# 创建数据目录
mkdir -p realtime_data

echo ""
echo "请选择要运行的程序："
echo "1. 测试AKShare安装"
echo "2. 获取实时行情数据（单次）"
echo "3. 定时获取实时数据"
echo "4. 查看使用说明"
echo "5. 退出"
echo ""

read -p "请输入选项 (1-5): " choice

case $choice in
    1)
        echo "运行测试脚本..."
        python test_akshare_realtime.py
        ;;
    2)
        echo "获取实时行情数据..."
        python get_a_share_realtime_data.py
        ;;
    3)
        echo "启动定时数据收集..."
        echo "按 Ctrl+C 停止程序"
        python schedule_realtime_data.py
        ;;
    4)
        echo "查看使用说明..."
        cat README.md | head -50
        echo ""
        echo "完整说明请查看 README.md 文件"
        ;;
    5)
        echo "退出程序"
        exit 0
        ;;
    *)
        echo "无效选项"
        ;;
esac

echo ""
echo "=========================================="
echo "程序执行完成"
echo "=========================================="