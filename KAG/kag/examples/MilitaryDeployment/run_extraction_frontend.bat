@echo off
REM KAG知识抽取前端启动脚本 (Windows)
echo ========================================
echo KAG 知识抽取系统 - 启动中...
echo ========================================
echo.

cd /d "%~dp0"

REM 尝试使用 python -m streamlit（更可靠的方式）
python -m streamlit run kag_extraction_frontend.py 2>&1

if errorlevel 1 (
    echo.
    echo ========================================
    echo 启动失败！可能的原因：
    echo 1. 未安装 streamlit，请运行: pip install streamlit
    echo 2. Python 不在 PATH 中
    echo 3. 查看上方的错误信息
    echo ========================================
    pause
    exit /b 1
)

pause

