import os
import sys

# 获取当前工作目录
current_dir = os.getcwd()
print(f"当前工作目录: {current_dir}")

# 构建文档的完整路径
doc_path = os.path.join(current_dir, "解决大模型幻觉的方法.docx")
print(f"文档绝对路径: {doc_path}")

# 检查文件是否存在
if os.path.exists(doc_path):
    file_size = os.path.getsize(doc_path)
    print(f"文档大小: {file_size} 字节")
else:
    print("文档不存在")

# 计算文档字数（近似）
try:
    import docx
    doc = docx.Document(doc_path)
    word_count = 0
    for paragraph in doc.paragraphs:
        word_count += len(paragraph.text.strip().split())
    print(f"文档字数（近似）: {word_count} 字")
except ImportError:
    print("无法导入docx库进行字数统计")