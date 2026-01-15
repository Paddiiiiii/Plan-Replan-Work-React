#!/bin/bash
# KAG知识抽取前端启动脚本 (Linux/Mac)

echo "========================================"
echo "KAG 知识抽取系统 - 启动中..."
echo "========================================"
echo ""

cd "$(dirname "$0")"

# 尝试使用 python -m streamlit（更可靠的方式）
python -m streamlit run kag_extraction_frontend.py

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "启动失败！可能的原因："
    echo "1. 未安装 streamlit，请运行: pip install streamlit"
    echo "2. Python 不在 PATH 中"
    echo "========================================"
    exit 1
fi

