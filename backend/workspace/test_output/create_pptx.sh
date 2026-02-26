#!/bin/bash
# 尝试使用 markitdown 创建 PPT

echo "尝试将 markdown 转换为 PPT..."

# 检查 markitdown 是否可用
if command -v python &> /dev/null; then
    echo "Python 可用"
    python -c "import markitdown; print('markitdown 已安装')" 2>/dev/null || echo "markitdown 未安装"
else
    echo "Python 不可用"
fi

echo "创建简单的 PPT 结构..."