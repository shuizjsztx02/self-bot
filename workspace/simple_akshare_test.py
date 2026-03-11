#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的AKShare测试脚本
测试实时行情数据获取
"""

import sys
import os
from datetime import datetime

def main():
    print("=" * 50)
    print("AKShare A股实时行情数据测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        # 尝试导入AKShare
        print("1. 导入AKShare...")
        import akshare as ak
        print("   ✅ AKShare导入成功")
        
        # 检查版本
        try:
            import pkg_resources
            version = pkg_resources.get_distribution("akshare").version
            print(f"   ✅ AKShare版本: {version}")
        except:
            print("   ℹ️ 无法获取AKShare版本信息")
        
        # 测试获取实时行情数据
        print("\n2. 测试获取实时行情数据...")
        try:
            # 尝试获取少量数据
            print("   正在获取A股实时行情数据...")
            data = ak.stock_zh_a_spot()
            
            if data is not None and not data.empty:
                print(f"   ✅ 成功获取数据！")
                print(f"   股票数量: {len(data)} 只")
                print(f"   数据列数: {len(data.columns)} 列")
                
                # 显示前几行数据
                print(f"\n   前3只股票数据:")
                print(data.head(3).to_string())
                
                # 显示列名
                print(f"\n   数据列名:")
                for i, col in enumerate(data.columns):
                    print(f"     {i+1:2d}. {col}")
                
                return True
            else:
                print("   ❌ 获取的数据为空")
                return False
                
        except Exception as e:
            print(f"   ❌ 获取数据失败: {e}")
            print("   可能的原因:")
            print("   - 网络连接问题")
            print("   - AKShare版本问题")
            print("   - 数据源暂时不可用")
            return False
            
    except ImportError as e:
        print(f"❌ 导入AKShare失败: {e}")
        print("请安装AKShare:")
        print("pip install akshare")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n" + "=" * 50)
        print("✅ 测试成功！AKShare可以正常工作")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("❌ 测试失败，请检查上述错误信息")
        print("=" * 50)
        sys.exit(1)