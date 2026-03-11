#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare实时行情数据测试脚本
"""

import sys
import os
from datetime import datetime

def test_akshare_installation():
    """测试AKShare是否安装成功"""
    print("=" * 50)
    print("AKShare安装测试")
    print("=" * 50)
    
    try:
        import akshare as ak
        print("✅ AKShare导入成功")
        
        # 检查版本
        try:
            import pkg_resources
            version = pkg_resources.get_distribution("akshare").version
            print(f"✅ AKShare版本: {version}")
        except:
            print("ℹ️ 无法获取AKShare版本信息")
        
        return True
    except ImportError as e:
        print(f"❌ AKShare导入失败: {e}")
        print("\n请安装AKShare:")
        print("pip install akshare")
        return False

def test_realtime_data():
    """测试实时行情数据获取"""
    print("\n" + "=" * 50)
    print("实时行情数据获取测试")
    print("=" * 50)
    
    try:
        import akshare as ak
        
        print("正在获取A股实时行情数据...")
        
        # 尝试获取实时数据
        realtime_data = ak.stock_zh_a_spot()
        
        if realtime_data is None or realtime_data.empty:
            print("❌ 获取到的数据为空")
            return False
        
        print(f"✅ 成功获取实时行情数据！")
        print(f"数据形状: {realtime_data.shape}")
        print(f"股票数量: {len(realtime_data)}")
        
        # 显示前5只股票
        print("\n前5只股票实时行情:")
        print(realtime_data[['代码', '名称', '最新价', '涨跌幅']].head(5).to_string())
        
        # 显示数据列
        print(f"\n数据列名: {list(realtime_data.columns)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取实时数据时出错: {e}")
        print("\n可能的原因:")
        print("1. 网络连接问题")
        print("2. 数据源暂时不可用")
        print("3. AKShare版本问题")
        return False

def test_specific_stocks():
    """测试获取指定股票数据"""
    print("\n" + "=" * 50)
    print("指定股票数据获取测试")
    print("=" * 50)
    
    try:
        import akshare as ak
        
        # 测试股票列表
        test_stocks = [
            '000001',  # 平安银行
            '000002',  # 万科A
            '600519',  # 贵州茅台
            '000858',  # 五粮液
            '002415'   # 海康威视
        ]
        
        print(f"测试股票代码: {test_stocks}")
        
        # 获取所有数据
        all_data = ak.stock_zh_a_spot()
        
        if all_data.empty:
            print("❌ 未获取到数据")
            return False
        
        # 筛选测试股票
        filtered_data = all_data[all_data['代码'].isin(test_stocks)]
        
        if filtered_data.empty:
            print("❌ 未找到测试股票")
            return False
        
        print(f"✅ 成功获取 {len(filtered_data)} 只测试股票的实时数据")
        print("\n测试股票实时行情:")
        print(filtered_data[['代码', '名称', '最新价', '涨跌幅', '成交量']].to_string())
        
        return True
        
    except Exception as e:
        print(f"❌ 测试指定股票时出错: {e}")
        return False

def main():
    """主函数"""
    print("AKShare实时行情数据测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # 测试1: 检查AKShare安装
    if not test_akshare_installation():
        print("\n❌ AKShare安装测试失败，请先安装AKShare")
        return
    
    # 测试2: 获取实时数据
    if not test_realtime_data():
        print("\n❌ 实时数据获取测试失败")
        return
    
    # 测试3: 获取指定股票数据
    test_specific_stocks()
    
    print("\n" + "=" * 50)
    print("✅ 所有测试完成！")
    print("=" * 50)
    
    print("\n下一步建议:")
    print("1. 运行主程序: python get_a_share_realtime_data.py")
    print("2. 查看生成的数据文件")
    print("3. 根据需求修改代码")

if __name__ == "__main__":
    main()