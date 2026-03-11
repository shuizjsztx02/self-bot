#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare A股实时行情数据获取工具
获取所有A股上市公司的实时行情数据
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import sys
import os

def get_all_a_share_realtime_data():
    """
    获取所有A股实时行情数据
    """
    print("=" * 60)
    print("A股实时行情数据获取工具")
    print(f"获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        print("正在获取A股实时行情数据...")
        
        # 获取所有A股实时行情数据
        realtime_data = ak.stock_zh_a_spot()
        
        if realtime_data.empty:
            print("❌ 未获取到数据，请检查网络连接或AKShare版本")
            return None
        
        print(f"✅ 成功获取数据！")
        print(f"股票数量: {len(realtime_data)} 只")
        print(f"数据列数: {len(realtime_data.columns)} 列")
        
        return realtime_data
        
    except Exception as e:
        print(f"❌ 获取数据时出错: {e}")
        print("可能的原因:")
        print("1. 网络连接问题")
        print("2. AKShare版本过旧")
        print("3. 数据源暂时不可用")
        return None

def get_specific_stocks_realtime(symbols):
    """
    获取指定股票的实时行情数据
    """
    print(f"正在获取指定股票实时行情数据...")
    
    try:
        # 先获取所有数据
        all_data = ak.stock_zh_a_spot()
        
        if all_data.empty:
            print("❌ 未获取到数据")
            return None
        
        # 筛选指定股票
        symbols_list = [str(s).zfill(6) for s in symbols]  # 确保6位代码
        filtered_data = all_data[all_data['代码'].isin(symbols_list)]
        
        if filtered_data.empty:
            print(f"❌ 未找到指定的股票代码: {symbols}")
            print(f"可用股票代码示例: {all_data['代码'].head(5).tolist()}")
            return None
        
        print(f"✅ 成功获取 {len(filtered_data)} 只指定股票的实时行情数据")
        return filtered_data
        
    except Exception as e:
        print(f"❌ 获取指定股票数据时出错: {e}")
        return None

def get_top_stocks_by_volume(data, top_n=20):
    """
    获取成交量最高的股票
    """
    if data is None or data.empty:
        return None
    
    # 按成交量降序排序
    sorted_data = data.sort_values('成交量', ascending=False)
    return sorted_data.head(top_n)

def get_top_stocks_by_change(data, top_n=20):
    """
    获取涨跌幅最高的股票
    """
    if data is None or data.empty:
        return None
    
    # 按涨跌幅降序排序（涨幅最高）
    sorted_data = data.sort_values('涨跌幅', ascending=False)
    return sorted_data.head(top_n)

def get_top_stocks_by_turnover(data, top_n=20):
    """
    获取换手率最高的股票
    """
    if data is None or data.empty:
        return None
    
    # 按换手率降序排序
    sorted_data = data.sort_values('换手率', ascending=False)
    return sorted_data.head(top_n)

def save_data_to_files(data, filename_prefix="a_share_realtime"):
    """
    保存数据到不同格式的文件
    """
    if data is None or data.empty:
        print("没有数据可保存")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 保存为CSV
    csv_file = f"{filename_prefix}_{timestamp}.csv"
    data.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"✅ CSV文件已保存: {csv_file}")
    
    # 保存为Excel
    excel_file = f"{filename_prefix}_{timestamp}.xlsx"
    data.to_excel(excel_file, index=False)
    print(f"✅ Excel文件已保存: {excel_file}")
    
    # 创建数据摘要
    summary_file = f"{filename_prefix}_summary_{timestamp}.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"A股实时行情数据摘要\n")
        f.write(f"获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"股票数量: {len(data)}\n")
        f.write(f"数据列数: {len(data.columns)}\n")
        f.write(f"数据列名: {list(data.columns)}\n")
        f.write(f"最新价格统计:\n")
        f.write(f"  平均最新价: {data['最新价'].mean():.2f}元\n")
        f.write(f"  最高最新价: {data['最新价'].max():.2f}元\n")
        f.write(f"  最低最新价: {data['最新价'].min():.2f}元\n")
        f.write(f"涨跌幅统计:\n")
        f.write(f"  平均涨跌幅: {data['涨跌幅'].mean():.2f}%\n")
        f.write(f"  最大涨幅: {data['涨跌幅'].max():.2f}%\n")
        f.write(f"  最大跌幅: {data['涨跌幅'].min():.2f}%\n")
        f.write(f"成交量统计:\n")
        f.write(f"  平均成交量: {data['成交量'].mean():,.0f}股\n")
        f.write(f"  最大成交量: {data['成交量'].max():,.0f}股\n")
        f.write(f"  最小成交量: {data['成交量'].min():,.0f}股\n")
    print(f"✅ 数据摘要已保存: {summary_file}")
    
    return csv_file, excel_file, summary_file

def display_data_summary(data):
    """
    显示数据摘要信息
    """
    if data is None or data.empty:
        print("没有数据可显示")
        return
    
    print("\n" + "=" * 60)
    print("数据摘要信息")
    print("=" * 60)
    
    # 显示前10行数据
    print("\n=== 前10只股票实时行情 ===")
    print(data[['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额']].head(10).to_string())
    
    # 基本统计信息
    print("\n=== 基本统计信息 ===")
    print(f"股票总数: {len(data)}")
    print(f"数据列数: {len(data.columns)}")
    print(f"数据列名: {list(data.columns)}")
    
    # 价格统计
    print("\n=== 价格统计 ===")
    print(f"平均最新价: {data['最新价'].mean():.2f}元")
    print(f"价格范围: {data['最新价'].min():.2f} - {data['最新价'].max():.2f}元")
    print(f"价格标准差: {data['最新价'].std():.2f}元")
    
    # 涨跌幅统计
    print("\n=== 涨跌幅统计 ===")
    print(f"平均涨跌幅: {data['涨跌幅'].mean():.2f}%")
    print(f"涨幅范围: {data['涨跌幅'].min():.2f}% - {data['涨跌幅'].max():.2f}%")
    
    # 成交量统计
    print("\n=== 成交量统计 ===")
    print(f"平均成交量: {data['成交量'].mean():,.0f}股")
    print(f"成交量范围: {data['成交量'].min():,.0f} - {data['成交量'].max():,.0f}股")
    
    # 成交额统计
    print("\n=== 成交额统计 ===")
    print(f"平均成交额: {data['成交额'].mean():,.0f}元")
    print(f"成交额范围: {data['成交额'].min():,.0f} - {data['成交额'].max():,.0f}元")

def display_top_performers(data):
    """
    显示表现最佳的股票
    """
    if data is None or data.empty:
        return
    
    print("\n" + "=" * 60)
    print("表现最佳股票排行榜")
    print("=" * 60)
    
    # 涨幅最高的股票
    top_gainers = get_top_stocks_by_change(data, 10)
    print("\n=== 涨幅最高的10只股票 ===")
    print(top_gainers[['代码', '名称', '最新价', '涨跌幅', '成交量']].to_string())
    
    # 成交量最高的股票
    top_volume = get_top_stocks_by_volume(data, 10)
    print("\n=== 成交量最高的10只股票 ===")
    print(top_volume[['代码', '名称', '最新价', '涨跌幅', '成交量']].to_string())
    
    # 换手率最高的股票
    top_turnover = get_top_stocks_by_turnover(data, 10)
    print("\n=== 换手率最高的10只股票 ===")
    print(top_turnover[['代码', '名称', '最新价', '涨跌幅', '换手率']].to_string())

def get_market_overview(data):
    """
    获取市场概览
    """
    if data is None or data.empty:
        return None
    
    print("\n" + "=" * 60)
    print("市场概览")
    print("=" * 60)
    
    # 上涨股票数量
    rising_stocks = len(data[data['涨跌幅'] > 0])
    falling_stocks = len(data[data['涨跌幅'] < 0])
    unchanged_stocks = len(data[data['涨跌幅'] == 0])
    
    print(f"上涨股票: {rising_stocks} 只 ({rising_stocks/len(data)*100:.1f}%)")
    print(f"下跌股票: {falling_stocks} 只 ({falling_stocks/len(data)*100:.1f}%)")
    print(f"平盘股票: {unchanged_stocks} 只 ({unchanged_stocks/len(data)*100:.1f}%)")
    
    # 涨停股票
    limit_up_stocks = len(data[data['涨跌幅'] >= 9.9])
    print(f"涨停股票: {limit_up_stocks} 只")
    
    # 跌停股票
    limit_down_stocks = len(data[data['涨跌幅'] <= -9.9])
    print(f"跌停股票: {limit_down_stocks} 只")
    
    # 总成交额
    total_turnover = data['成交额'].sum()
    print(f"总成交额: {total_turnover:,.0f} 元")
    
    # 平均换手率
    avg_turnover_rate = data['换手率'].mean()
    print(f"平均换手率: {avg_turnover_rate:.2f}%")
    
    return {
        'rising_stocks': rising_stocks,
        'falling_stocks': falling_stocks,
        'unchanged_stocks': unchanged_stocks,
        'limit_up_stocks': limit_up_stocks,
        'limit_down_stocks': limit_down_stocks,
        'total_turnover': total_turnover,
        'avg_turnover_rate': avg_turnover_rate
    }

def main():
    """
    主函数
    """
    print("=" * 60)
    print("AKShare A股实时行情数据获取工具")
    print("=" * 60)
    
    # 检查是否安装AKShare
    try:
        import akshare
        print("✅ AKShare已安装")
    except ImportError:
        print("❌ AKShare未安装，请先安装:")
        print("pip install akshare")
        return
    
    # 获取所有A股实时行情数据
    realtime_data = get_all_a_share_realtime_data()
    
    if realtime_data is not None:
        # 显示数据摘要
        display_data_summary(realtime_data)
        
        # 显示表现最佳的股票
        display_top_performers(realtime_data)
        
        # 获取市场概览
        get_market_overview(realtime_data)
        
        # 保存数据
        save_files = save_data_to_files(realtime_data)
        
        # 示例：获取指定股票的实时行情
        print("\n" + "=" * 60)
        print("示例：获取指定股票的实时行情")
        print("=" * 60)
        
        # 一些常见股票的代码
        sample_stocks = ['000001', '000002', '600519', '000858', '002415']
        specific_data = get_specific_stocks_realtime(sample_stocks)
        
        if specific_data is not None:
            print("\n指定股票实时行情:")
            print(specific_data[['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额']].to_string())
        
        print("\n" + "=" * 60)
        print("✅ 程序执行完成！")
        print("=" * 60)

if __name__ == "__main__":
    main()