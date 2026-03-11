#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取贵州茅台(600519)最近一年的日K线行情数据
使用AKshare库
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import json

def get_maotai_stock_data():
    """
    获取贵州茅台(600519)最近一年的日K线数据
    """
    # 股票代码
    symbol = "600519"
    
    # 计算日期：最近一年
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    # 格式化日期为AKshare需要的格式
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")
    
    print(f"正在获取贵州茅台({symbol})股票数据...")
    print(f"时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
    print("-" * 50)
    
    try:
        # 获取日K线数据（前复权）
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date_str,
            end_date=end_date_str,
            adjust="qfq"  # 前复权
        )
        
        if df.empty:
            print("未获取到数据，请检查网络连接或股票代码")
            return None
        
        # 显示数据基本信息
        print(f"数据获取成功！共获取 {len(df)} 条记录")
        print(f"数据列: {list(df.columns)}")
        print("\n前5条数据:")
        print(df.head())
        print("\n后5条数据:")
        print(df.tail())
        
        # 数据统计信息
        print("\n数据统计信息:")
        print(df.describe())
        
        # 保存数据到CSV文件
        csv_filename = f"maotai_{symbol}_daily_kline_{start_date_str}_{end_date_str}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"\n数据已保存到: {csv_filename}")
        
        # 保存数据到JSON文件（便于查看）
        json_filename = f"maotai_{symbol}_daily_kline_{start_date_str}_{end_date_str}.json"
        # 将日期列转换为字符串格式
        df_json = df.copy()
        if '日期' in df_json.columns:
            df_json['日期'] = df_json['日期'].astype(str)
        
        # 转换为字典列表格式
        data_list = df_json.to_dict('records')
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                "symbol": symbol,
                "name": "贵州茅台",
                "period": "daily",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "total_records": len(df),
                "data": data_list
            }, f, ensure_ascii=False, indent=2)
        
        print(f"JSON数据已保存到: {json_filename}")
        
        return df
        
    except Exception as e:
        print(f"获取数据时出错: {e}")
        print("\n可能的原因:")
        print("1. 请确保已安装AKshare库: pip install akshare")
        print("2. 检查网络连接")
        print("3. 股票代码是否正确")
        return None

def analyze_stock_data(df):
    """
    分析股票数据
    """
    if df is None:
        return
    
    print("\n" + "="*50)
    print("股票数据分析报告")
    print("="*50)
    
    # 计算基本统计
    if '收盘' in df.columns:
        latest_close = df['收盘'].iloc[-1]
        first_close = df['收盘'].iloc[0]
        price_change = latest_close - first_close
        price_change_pct = (price_change / first_close) * 100
        
        print(f"期初收盘价: {first_close:.2f}")
        print(f"期末收盘价: {latest_close:.2f}")
        print(f"价格变动: {price_change:+.2f} ({price_change_pct:+.2f}%)")
        
        # 最高价和最低价
        highest_price = df['最高'].max()
        lowest_price = df['最低'].min()
        highest_date = df.loc[df['最高'] == highest_price, '日期'].iloc[0]
        lowest_date = df.loc[df['最低'] == lowest_price, '日期'].iloc[0]
        
        print(f"最高价: {highest_price:.2f} (日期: {highest_date})")
        print(f"最低价: {lowest_price:.2f} (日期: {lowest_date})")
        
        # 成交量分析
        if '成交量' in df.columns:
            avg_volume = df['成交量'].mean()
            max_volume = df['成交量'].max()
            max_volume_date = df.loc[df['成交量'] == max_volume, '日期'].iloc[0]
            
            print(f"\n成交量分析:")
            print(f"平均成交量: {avg_volume:,.0f} 手")
            print(f"最大成交量: {max_volume:,.0f} 手 (日期: {max_volume_date})")
        
        # 涨跌天数统计
        if '涨跌幅' in df.columns:
            up_days = (df['涨跌幅'] > 0).sum()
            down_days = (df['涨跌幅'] < 0).sum()
            flat_days = (df['涨跌幅'] == 0).sum()
            
            print(f"\n涨跌天数统计:")
            print(f"上涨天数: {up_days} ({up_days/len(df)*100:.1f}%)")
            print(f"下跌天数: {down_days} ({down_days/len(df)*100:.1f}%)")
            print(f"平盘天数: {flat_days} ({flat_days/len(df)*100:.1f}%)")

def main():
    """
    主函数
    """
    print("="*60)
    print("贵州茅台(600519)日K线数据获取工具")
    print("="*60)
    
    # 获取数据
    df = get_maotai_stock_data()
    
    # 分析数据
    if df is not None:
        analyze_stock_data(df)
    
    print("\n" + "="*60)
    print("数据获取和分析完成！")
    print("="*60)

if __name__ == "__main__":
    main()