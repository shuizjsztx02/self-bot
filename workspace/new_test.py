#!/usr/bin/env python3
"""
新的简单测试脚本
测试智能助手的基本功能
"""

import os
import sys
from datetime import datetime

def test_file_operations():
    """测试文件操作"""
    print("=== 测试文件操作 ===")
    
    # 创建测试文件
    test_content = "这是一个测试文件\n创建时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # 写入文件
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write(test_content)
        print("✅ 文件写入成功")
        
        # 读取文件
        with open("test_output.txt", "r", encoding="utf-8") as f:
            content = f.read()
        print("✅ 文件读取成功")
        print(f"文件内容:\n{content}")
        
        # 检查文件是否存在
        if os.path.exists("test_output.txt"):
            print("✅ 文件存在性验证成功")
            file_size = os.path.getsize("test_output.txt")
            print(f"文件大小: {file_size} 字节")
        
        return True
    except Exception as e:
        print(f"❌ 文件操作失败: {e}")
        return False

def test_math_operations():
    """测试数学运算"""
    print("\n=== 测试数学运算 ===")
    
    try:
        # 基本运算
        result1 = 10 + 5
        print(f"✅ 加法: 10 + 5 = {result1}")
        
        result2 = 20 - 8
        print(f"✅ 减法: 20 - 8 = {result2}")
        
        result3 = 6 * 7
        print(f"✅ 乘法: 6 * 7 = {result3}")
        
        result4 = 15 / 3
        print(f"✅ 除法: 15 / 3 = {result4}")
        
        # 幂运算
        result5 = 2 ** 10
        print(f"✅ 幂运算: 2^10 = {result5}")
        
        return True
    except Exception as e:
        print(f"❌ 数学运算失败: {e}")
        return False

def test_string_operations():
    """测试字符串操作"""
    print("\n=== 测试字符串操作 ===")
    
    try:
        text = "Hello, 智能助手!"
        
        # 字符串长度
        length = len(text)
        print(f"✅ 字符串长度: '{text}' 的长度是 {length}")
        
        # 字符串切片
        part1 = text[:5]
        print(f"✅ 字符串切片: 前5个字符是 '{part1}'")
        
        part2 = text[-6:]
        print(f"✅ 字符串切片: 后6个字符是 '{part2}'")
        
        # 字符串连接
        new_text = text + " 欢迎使用！"
        print(f"✅ 字符串连接: '{new_text}'")
        
        # 字符串查找
        if "智能" in text:
            print("✅ 字符串查找: 找到 '智能'")
        
        # 字符串替换
        replaced = text.replace("Hello", "你好")
        print(f"✅ 字符串替换: '{replaced}'")
        
        return True
    except Exception as e:
        print(f"❌ 字符串操作失败: {e}")
        return False

def test_list_operations():
    """测试列表操作"""
    print("\n=== 测试列表操作 ===")
    
    try:
        # 创建列表
        fruits = ["苹果", "香蕉", "橙子", "葡萄", "芒果"]
        print(f"✅ 创建列表: {fruits}")
        
        # 添加元素
        fruits.append("草莓")
        print(f"✅ 添加元素: {fruits}")
        
        # 删除元素
        removed = fruits.pop(1)
        print(f"✅ 删除元素: 移除 '{removed}'，剩余 {fruits}")
        
        # 列表长度
        print(f"✅ 列表长度: {len(fruits)} 个元素")
        
        # 列表排序
        sorted_fruits = sorted(fruits)
        print(f"✅ 列表排序: {sorted_fruits}")
        
        # 列表推导式
        numbers = [1, 2, 3, 4, 5]
        squares = [x**2 for x in numbers]
        print(f"✅ 列表推导式: {numbers} 的平方是 {squares}")
        
        return True
    except Exception as e:
        print(f"❌ 列表操作失败: {e}")
        return False

def test_dictionary_operations():
    """测试字典操作"""
    print("\n=== 测试字典操作 ===")
    
    try:
        # 创建字典
        student = {
            "name": "张三",
            "age": 20,
            "major": "计算机科学",
            "grades": {"数学": 95, "英语": 88, "编程": 92}
        }
        print(f"✅ 创建字典: {student}")
        
        # 访问值
        print(f"✅ 访问值: 姓名 - {student['name']}, 年龄 - {student['age']}")
        
        # 添加新键值对
        student["email"] = "zhangsan@example.com"
        print(f"✅ 添加键值对: {student}")
        
        # 更新值
        student["age"] = 21
        print(f"✅ 更新值: 年龄更新为 {student['age']}")
        
        # 遍历字典
        print("✅ 遍历字典:")
        for key, value in student.items():
            if key != "grades":
                print(f"  {key}: {value}")
        
        # 嵌套字典访问
        print(f"✅ 嵌套字典访问: 数学成绩 - {student['grades']['数学']}")
        
        return True
    except Exception as e:
        print(f"❌ 字典操作失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始运行简单测试")
    print("=" * 50)
    
    # 运行所有测试
    tests = [
        ("文件操作", test_file_operations),
        ("数学运算", test_math_operations),
        ("字符串操作", test_string_operations),
        ("列表操作", test_list_operations),
        ("字典操作", test_dictionary_operations)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            failed += 1
    
    # 显示测试结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    print(f"✅ 通过的测试: {passed}")
    print(f"❌ 失败的测试: {failed}")
    print(f"📈 成功率: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 所有测试通过！系统运行正常。")
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查问题。")
    
    # 清理测试文件
    try:
        if os.path.exists("test_output.txt"):
            os.remove("test_output.txt")
            print("\n🧹 已清理测试文件")
    except:
        pass
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)