#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时获取A股实时行情数据脚本
"""

import akshare as ak
import pandas as pd
import time
import schedule
from datetime import datetime
import os

class RealtimeDataCollector:
    """实时数据收集器"""
    
    def __init__(self, data_dir="realtime_data"):
        """
        初始化收集器
        
        Args:
            data_dir: 数据保存目录
        """
        self.data_dir = data_dir
        self.create_data_dir()
        
    def create_data_dir(self):
        """创建数据目录"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"✅ 创建数据目录: {self.data_dir}")
    
    def get_realtime_data(self):
        """获取实时数据"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在获取实时行情数据...")
            
            data = ak.stock_zh_a_spot()
            
            if data is None or data.empty:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 获取数据失败")
                return None
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 成功获取 {len(data)} 只股票数据")
            return data
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 获取数据时出错: {e}")
            return None
    
    def save_data(self, data, filename_prefix="realtime"):
        """保存数据"""
        if data is None or data.empty:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # CSV文件
        csv_file = os.path.join(self.data_dir, f"{filename_prefix}_{timestamp}.csv")
        data.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        # 数据摘要
        summary_file = os.path.join(self.data_dir, f"summary_{timestamp}.txt")
        self.create_summary(data, summary_file)
        
        return csv_file, summary_file
    
    def create_summary(self, data, summary_file):
        """创建数据摘要"""
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"A股实时行情数据摘要\n")
            f.write(f"获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"股票数量: {len(data)}\n")
            
            # 市场统计
            rising = len(data[data['涨跌幅'] > 0])
            falling = len(data[data['涨跌幅'] < 0])
            unchanged = len(data[data['涨跌幅'] == 0])
            
            f.write(f"\n市场统计:\n")
            f.write(f"  上涨股票: {rising} 只 ({rising/len(data)*100:.1f}%)\n")
            f.write(f"  下跌股票: {falling} 只 ({falling/len(data)*100:.1f}%)\n")
            f.write(f"  平盘股票: {unchanged} 只 ({unchanged/len(data)*100:.1f}%)\n")
            
            # 涨停跌停
            limit_up = len(data[data['涨跌幅'] >= 9.9])
            limit_down = len(data[data['涨跌幅'] <= -9.9])
            f.write(f"  涨停股票: {limit_up} 只\n")
            f.write(f"  跌停股票: {limit_down} 只\n")
            
            # 价格统计
            f.write(f"\n价格统计:\n")
            f.write(f"  平均价格: {data['最新价'].mean():.2f}元\n")
            f.write(f"  最高价格: {data['最新价'].max():.2f}元\n")
            f.write(f"  最低价格: {data['最新价'].min():.2f}元\n")
            
            # 成交量统计
            f.write(f"\n成交量统计:\n")
            f.write(f"  总成交量: {data['成交量'].sum():,.0f}股\n")
            f.write(f"  平均成交量: {data['成交量'].mean():,.0f}股\n")
            
            # 成交额统计
            f.write(f"\n成交额统计:\n")
            f.write(f"  总成交额: {data['成交额'].sum():,.0f}元\n")
            
            # 涨幅榜前5
            f.write(f"\n涨幅榜前5:\n")
            top_gainers = data.sort_values('涨跌幅', ascending=False).head(5)
            for idx, row in top_gainers.iterrows():
                f.write(f"  {row['代码']} {row['名称']}: {row['涨跌幅']:.2f}% ({row['最新价']:.2f}元)\n")
            
            # 跌幅榜前5
            f.write(f"\n跌幅榜前5:\n")
            top_losers = data.sort_values('涨跌幅', ascending=True).head(5)
            for idx, row in top_losers.iterrows():
                f.write(f"  {row['代码']} {row['名称']}: {row['涨跌幅']:.2f}% ({row['最新价']:.2f}元)\n")
    
    def collect_once(self):
        """单次收集任务"""
        print(f"\n{'='*60}")
        print(f"开始收集实时数据 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"{'='*60}")
        
        data = self.get_realtime_data()
        
        if data is not None:
            saved_files = self.save_data(data)
            if saved_files:
                csv_file, summary_file = saved_files
                print(f"✅ 数据已保存:")
                print(f"  CSV文件: {csv_file}")
                print(f"  摘要文件: {summary_file}")
            
            # 显示简要信息
            self.display_brief_info(data)
        
        print(f"{'='*60}")
    
    def display_brief_info(self, data):
        """显示简要信息"""
        print(f"\n📊 市场简要信息:")
        print(f"  股票总数: {len(data)}")
        
        # 涨跌统计
        rising = len(data[data['涨跌幅'] > 0])
        falling = len(data[data['涨跌幅'] < 0])
        print(f"  上涨: {rising}只 ({rising/len(data)*100:.1f}%)")
        print(f"  下跌: {falling}只 ({falling/len(data)*100:.1f}%)")
        
        # 涨停跌停
        limit_up = len(data[data['涨跌幅'] >= 9.9])
        limit_down = len(data[data['涨跌幅'] <= -9.9])
        print(f"  涨停: {limit_up}只, 跌停: {limit_down}只")
        
        # 总成交额
        total_turnover = data['成交额'].sum()
        print(f"  总成交额: {total_turnover/1e8:.2f}亿元")
        
        # 涨幅榜
        print(f"\n📈 涨幅榜前3:")
        top_gainers = data.sort_values('涨跌幅', ascending=False).head(3)
        for idx, row in top_gainers.iterrows():
            print(f"  {row['代码']} {row['名称']}: {row['涨跌幅']:.2f}% ({row['最新价']:.2f}元)")
        
        # 成交额榜
        print(f"\n💰 成交额榜前3:")
        top_turnover = data.sort_values('成交额', ascending=False).head(3)
        for idx, row in top_turnover.iterrows():
            print(f"  {row['代码']} {row['名称']}: {row['成交额']/1e8:.2f}亿元")

def main():
    """主函数"""
    print("=" * 60)
    print("A股实时行情数据定时收集系统")
    print("=" * 60)
    
    # 创建收集器
    collector = RealtimeDataCollector()
    
    print("\n📅 定时任务设置:")
    print("  1. 每5分钟收集一次数据")
    print("  2. 数据保存在 'realtime_data' 目录")
    print("  3. 按 Ctrl+C 停止程序")
    print("\n⏰ 开始定时收集...")
    
    # 立即执行一次
    collector.collect_once()
    
    # 设置定时任务
    schedule.every(5).minutes.do(collector.collect_once)
    
    # 保持程序运行
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 程序已停止")
        print("感谢使用A股实时行情数据收集系统！")

if __name__ == "__main__":
    # 检查是否安装AKShare
    try:
        import akshare
    except ImportError:
        print("❌ AKShare未安装，请先安装:")
        print("pip install akshare")
        exit(1)
    
    main()