#!/usr/bin/env python3
"""
简单的测试脚本
用于演示智能助手的功能
"""

def hello_world():
    """打印Hello World"""
    print("Hello, World!")
    return "Hello, World!"

def add_numbers(a, b):
    """两个数字相加"""
    return a + b

def test_operations():
    """测试各种操作"""
    print("=== 开始测试 ===")
    
    # 测试hello_world
    result1 = hello_world()
    print(f"测试1: {result1}")
    
    # 测试加法
    result2 = add_numbers(5, 3)
    print(f"测试2: 5 + 3 = {result2}")
    
    # 测试更多操作
    numbers = [1, 2, 3, 4, 5]
    total = sum(numbers)
    print(f"测试3: 列表 {numbers} 的总和 = {total}")
    
    # 测试字符串操作
    text = "这是一个测试字符串"
    print(f"测试4: 字符串长度 - '{text}' 的长度是 {len(text)}")
    
    print("=== 测试完成 ===")
    return True

if __name__ == "__main__":
    # 运行测试
    success = test_operations()
    
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 测试失败！")