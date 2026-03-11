#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时收集A股实时行情数据
每5分钟自动获取一次数据
"""

import akshare as ak
import pandas as pd
import schedule
import time
import os
from datetime import datetime
import sys

def create_data_directory():
    """创建数据存储目录"""
    data_dir = "realtime_data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"✅ 创建数据目录: {data_dir}")
    return data_dir

def is_trading_time():
    """判断当前是否为交易时间"""
    now = datetime.now()
    weekday = now.weekday()  # 0-6，周一到周日
    
    # 周末不交易
    if weekday >= 5:
        return False
    
    # 交易时间：9:30-11:30, 13:00-15:00
    current_time = now.time()
    
    # 上午交易时间
    morning_start = datetime.strptime("09:30:00", "%H:%M:%S").time()
    morning_end = datetime.strptime("11:30:00", "%H:%M:%S").time()
    
    # 下午交易时间
    afternoon_start = datetime.strptime("13:00:00", "%H:%M:%S").time()
    afternoon_end = datetime.strptime("15:00:00", "%H:%M:%S").time()
    
    # 判断是否在交易时间内
    if (morning_start <= current_time <= morning_end) or \
       (afternoon_start <= current_time <= afternoon_end):
        return True
    
    return False

def collect_realtime_data():
    """收集实时行情数据"""
    current_time = datetime.now()
    timestamp = current_time.strftime('%Y%m%d_%H%M%S')
    
    print(f"\n[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] 开始收集实时行情数据...")
    
    # 检查是否为交易时间
    if not is_trading_time():
        print("   ℹ️ 当前为非交易时间，跳过数据收集")
        return
    
    try:
        # 获取实时数据
        print("   正在获取A股实时行情数据...")
        data = ak.stock_zh_a_spot()
        
        if data is None or data.empty:
            print("   ❌ 获取的数据为空")
            return
        
        print(f"   ✅ 成功获取 {len(data)} 只股票数据")
        
        # 创建数据目录
        data_dir = create_data_directory()
        
        # 保存为CSV
        csv_filename = os.path.join(data_dir, f'a_share_realtime_{timestamp}.csv')
        data.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"   ✅ CSV文件已保存: {csv_filename}")
        
        # 保存为Excel（每小时保存一次）
        if current_time.minute == 0:
            excel_filename = os.path.join(data_dir, f'a_share_realtime_{timestamp}.xlsx')
            data.to_excel(excel_filename, index=False)
            print(f"   ✅ Excel文件已保存: {excel_filename}")
        
        # 生成数据摘要
        generate_data_summary(data, timestamp, data_dir)
        
    except Exception as e:
        print(f"   ❌ 收集数据失败: {e}")

def generate_data_summary(data, timestamp, data_dir):
    """生成数据摘要报告"""
    try:
        summary_file = os.path.join(data_dir, f'summary_{timestamp}.txt')
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("A股实时行情数据摘要\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            # 市场概况
            f.write("=== 市场概况 ===\n")
            f.write(f"股票总数: {len(data)}\n")
            
            # 涨跌统计
            up_count = len(data[data['涨跌幅'] > 0])
            down_count = len(data[data['涨跌幅'] < 0])
            flat_count = len(data[data['涨跌幅'] == 0])
            
            f.write(f"上涨股票: {up_count} 只 ({up_count/len(data)*100:.1f}%)\n")
            f.write(f"下跌股票: {down_count} 只 ({down_count/len(data)*100:.1f}%)\n")
            f.write(f"平盘股票: {flat_count} 只 ({flat_count/len(data)*100:.1f}%)\n\n")
            
            # 涨停跌停统计
            limit_up_count = len(data[data['涨跌幅'] >= 9.9])
            limit_down_count = len(data[data['涨跌幅'] <= -9.9])
            
            f.write(f"涨停股票: {limit_up_count} 只\n")
            f.write(f"跌停股票: {limit_down_count} 只\n\n")
            
            # 涨幅榜TOP10
            f.write("=== 涨幅榜TOP10 ===\n")
            top_gainers = data.nlargest(10, '涨跌幅')
            for idx, (_, row) in enumerate(top_gainers.iterrows(), 1):
                f.write(f"{idx:2d}. {row['代码']} {row['名称']}: {row['最新价']:.2f}元 "
                       f"({row['涨跌幅']:+.2f}%) 成交量:{row['成交量']:,}手\n")
            
            f.write("\n")
            
            # 成交额榜TOP10
            f.write("=== 成交额榜TOP10 ===\n")
            top_volume = data.nlargest(10, '成交额')
            for idx, (_, row) in enumerate(top_volume.iterrows(), 1):
                f.write(f"{idx:2d}. {row['代码']} {row['名称']}: {row['最新价']:.2f}元 "
                       f"成交额:{row['成交额']:.2f}万元 换手率:{row['换手率']:.2f}%\n")
            
            f.write("\n")
            
            # 价格统计
            f.write("=== 价格统计 ===\n")
            f.write(f"平均价格: {data['最新价'].mean():.2f}元\n")
            f.write(f"最高价格: {data['最新价'].max():.2f}元\n")
            f.write(f"最低价格: {data['最新价'].min():.2f}元\n")
            f.write(f"价格中位数: {data['最新价'].median():.2f}元\n")
            
        print(f"   ✅ 数据摘要已生成: {summary_file}")
        
    except Exception as e:
        print(f"   ⚠️ 生成数据摘要失败: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("A股实时行情数据定时收集系统")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 创建日志目录
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 设置定时任务
    print("\n📅 定时任务设置:")
    print("  • 每5分钟收集一次数据")
    print("  • 仅在交易时间运行")
    print("  • 数据保存到 realtime_data/ 目录")
    print("  • 按 Ctrl+C 停止程序\n")
    
    # 立即执行一次
    collect_realtime_data()
    
    # 设置定时任务
    schedule.every(5).minutes.do(collect_realtime_data)
    
    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n程序已停止")
        print(f"停止时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sys.exit(0)

if __name__ == "__main__":
    # 检查依赖
    try:
        import akshare as ak
        import pandas as pd
        import schedule
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请安装依赖: pip install akshare pandas schedule")
        sys.exit(1)
    
    main()