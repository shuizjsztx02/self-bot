@echo off
echo ========================================
echo       文档生成工具
echo ========================================
echo.

echo 已创建的Markdown文档：
echo 1. 代码设计规范.md
echo 2. 总体方案设计.md
echo 3. 硬件电路布设.md
echo.

echo 文档内容概要：
echo.
type "代码设计规范.md" | findstr /B "#" /C:"##"
echo.
type "总体方案设计.md" | findstr /B "#" /C:"##"
echo.
type "硬件电路布设.md" | findstr /B "#" /C:"##"
echo.

echo ========================================
echo 使用说明：
echo 1. 这些Markdown文档可以直接用文本编辑器查看
echo 2. 可以使用Markdown编辑器转换为PDF
echo 3. 推荐使用Typora、VS Code等工具
echo 4. 也可以使用在线转换工具
echo ========================================
echo.

echo 文件统计：
for %%f in (*.md) do (
    for /f %%i in ('type "%%f" ^| find /c /v ""') do (
        echo %%f - 约%%i行
    )
)
echo.

pause