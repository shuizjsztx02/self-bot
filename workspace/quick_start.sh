#!/bin/bash

# A股实时行情数据获取工具 - 快速启动脚本

echo "=========================================="
echo "  A股实时行情数据获取工具 - 快速启动"
echo "=========================================="
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python版本: $PYTHON_VERSION"

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ 未找到pip3，请先安装pip3"
    exit 1
fi

echo "✅ pip3已安装"

# 创建虚拟环境（可选）
read -p "是否创建虚拟环境？(y/n): " create_venv
if [[ $create_venv == "y" || $create_venv == "Y" ]]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ 虚拟环境已激活"
fi

# 安装依赖
echo ""
echo "安装依赖..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ 依赖安装成功"
else
    echo "❌ 依赖安装失败，尝试使用国内镜像..."
    pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 测试AKShare
echo ""
echo "测试AKShare安装..."
python3 simple_akshare_test.py

if [ $? -eq 0 ]; then
    echo "✅ AKShare测试成功"
else
    echo "❌ AKShare测试失败"
    exit 1
fi

# 显示菜单
echo ""
echo "=========================================="
echo "  请选择要执行的操作："
echo "=========================================="
echo "1. 获取实时行情数据"
echo "2. 启动定时数据收集"
echo "3. 查看配置"
echo "4. 测试所有功能"
echo "5. 退出"
echo "=========================================="

read -p "请输入选项 (1-5): " choice

case $choice in
    1)
        echo "执行实时数据获取..."
        python3 get_a_share_realtime_data.py
        ;;
    2)
        echo "启动定时数据收集..."
        python3 schedule_data_collection.py
        ;;
    3)
        echo "查看配置..."
        python3 config_realtime.py
        ;;
    4)
        echo "测试所有功能..."
        echo "1. 测试AKShare..."
        python3 simple_akshare_test.py
        echo ""
        echo "2. 测试实时数据获取..."
        python3 get_a_share_realtime_data.py
        echo ""
        echo "3. 查看配置..."
        python3 config_realtime.py
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
echo "  程序执行完成"
echo "=========================================="

# 如果使用了虚拟环境，询问是否退出
if [[ $create_venv == "y" || $create_venv == "Y" ]]; then
    read -p "是否退出虚拟环境？(y/n): " exit_venv
    if [[ $exit_venv == "y" || $exit_venv == "Y" ]]; then
        deactivate
        echo "✅ 已退出虚拟环境"
    fi
fi