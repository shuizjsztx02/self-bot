#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AKshare是否正常工作
"""

try:
    import akshare as ak
    import pandas as pd
    print("✅ AKshare导入成功!")
    print(f"AKshare版本: {ak.__version__}")
    
    # 测试获取股票列表
    print("\n测试获取股票列表...")
    try:
        stock_list = ak.stock_zh_a_spot_em()
        if not stock_list.empty:
            print(f"✅ 获取到 {len(stock_list)} 只股票信息")
            # 查找贵州茅台
            maotai = stock_list[stock_list['代码'] == '600519']
            if not maotai.empty:
                print(f"✅ 找到贵州茅台: {maotai['名称'].iloc[0]}")
                print(f"   最新价: {maotai['最新价'].iloc[0]}")
                print(f"   涨跌幅: {maotai['涨跌幅'].iloc[0]}%")
            else:
                print("⚠️ 未找到贵州茅台(600519)")
        else:
            print("❌ 未获取到股票列表")
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
    
    # 测试获取简单数据
    print("\n测试获取简单历史数据...")
    try:
        # 获取最近5天的数据
        test_data = ak.stock_zh_a_hist(
            symbol="000001",  # 平安银行，通常有数据
            period="daily",
            start_date="20250301",
            end_date="20250305",
            adjust="qfq"
        )
        if not test_data.empty:
            print(f"✅ 获取到 {len(test_data)} 条历史数据")
            print("数据列:", list(test_data.columns))
        else:
            print("❌ 未获取到历史数据")
    except Exception as e:
        print(f"❌ 获取历史数据失败: {e}")
    
except ImportError as e:
    print("❌ AKshare导入失败!")
    print(f"错误信息: {e}")
    print("\n请安装AKshare:")
    print("pip install akshare")
    print("或")
    print("pip install -r requirements.txt")

print("\n" + "="*50)
print("测试完成!")
print("="*50)