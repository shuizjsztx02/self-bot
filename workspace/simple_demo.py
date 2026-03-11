#!/usr/bin/env python3
"""
简单演示脚本
展示智能助手的基本功能
"""

print("🎯 智能助手功能演示")
print("=" * 40)

# 1. 基本输出
print("1. 基本输出功能:")
print("   Hello, World!")
print("   你好，世界！")

# 2. 数学计算
print("\n2. 数学计算:")
a = 15
b = 7
print(f"   {a} + {b} = {a + b}")
print(f"   {a} - {b} = {a - b}")
print(f"   {a} × {b} = {a * b}")
print(f"   {a} ÷ {b} = {a / b:.2f}")

# 3. 字符串操作
print("\n3. 字符串操作:")
text = "智能助手测试"
print(f"   原始字符串: {text}")
print(f"   字符串长度: {len(text)}")
print(f"   大写转换: {text.upper()}")
print(f"   小写转换: {text.lower()}")

# 4. 列表操作
print("\n4. 列表操作:")
fruits = ["苹果", "香蕉", "橙子", "葡萄"]
print(f"   水果列表: {fruits}")
print(f"   第一个水果: {fruits[0]}")
print(f"   最后一个水果: {fruits[-1]}")
print(f"   水果数量: {len(fruits)}")

# 5. 循环和条件
print("\n5. 循环和条件:")
print("   数字1-5:")
for i in range(1, 6):
    if i % 2 == 0:
        print(f"     {i} (偶数)")
    else:
        print(f"     {i} (奇数)")

# 6. 函数定义
print("\n6. 函数定义:")

def greet(name):
    return f"你好，{name}！欢迎使用智能助手。"

print(f"   {greet('张三')}")
print(f"   {greet('李四')}")

# 7. 文件操作演示
print("\n7. 文件操作演示:")
try:
    # 写入文件
    with open("demo_output.txt", "w", encoding="utf-8") as f:
        f.write("这是一个演示文件\n")
        f.write("创建于智能助手测试\n")
        f.write("功能正常！\n")
    print("   ✅ 文件写入成功")
    
    # 读取文件
    with open("demo_output.txt", "r", encoding="utf-8") as f:
        content = f.read()
    print("   ✅ 文件读取成功")
    print(f"   文件内容:\n{content}")
    
    # 清理文件
    import os
    if os.path.exists("demo_output.txt"):
        os.remove("demo_output.txt")
        print("   ✅ 文件清理成功")
        
except Exception as e:
    print(f"   ❌ 文件操作失败: {e}")

print("\n" + "=" * 40)
print("✨ 演示完成！智能助手功能正常。")
print("=" * 40)