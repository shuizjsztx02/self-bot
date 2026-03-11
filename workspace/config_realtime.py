#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股实时行情数据获取配置
"""

# ==================== 基础配置 ====================

# 数据保存配置
DATA_CONFIG = {
    'save_csv': True,           # 是否保存为CSV格式
    'save_excel': True,         # 是否保存为Excel格式
    'save_json': False,         # 是否保存为JSON格式
    'data_directory': 'realtime_data',  # 数据保存目录
    'log_directory': 'logs',    # 日志保存目录
}

# 监控股票列表（可自定义）
MONITOR_STOCKS = [
    '000001',  # 平安银行
    '600519',  # 贵州茅台
    '000858',  # 五粮液
    '300750',  # 宁德时代
    '002594',  # 比亚迪
    '600036',  # 招商银行
    '601318',  # 中国平安
    '000333',  # 美的集团
    '000002',  # 万科A
    '601888',  # 中国中免
]

# 预警配置
ALERT_CONFIG = {
    'price_change_threshold': 5.0,     # 价格变动预警阈值（%）
    'volume_change_threshold': 200,    # 成交量变动预警阈值（%）
    'turnover_threshold': 20.0,        # 换手率预警阈值（%）
}

# ==================== 定时任务配置 ====================

SCHEDULE_CONFIG = {
    'collection_interval': 5,          # 数据收集间隔（分钟）
    'only_trading_hours': True,        # 是否仅在交易时间运行
    'trading_hours': {                 # 交易时间配置
        'morning_start': '09:30',
        'morning_end': '11:30',
        'afternoon_start': '13:00',
        'afternoon_end': '15:00',
    },
    'weekend_skip': True,              # 周末是否跳过
}

# ==================== 数据过滤配置 ====================

FILTER_CONFIG = {
    'min_price': 1.0,                  # 最低价格过滤（元）
    'max_price': 1000.0,               # 最高价格过滤（元）
    'min_volume': 1000,                # 最低成交量过滤（手）
    'min_market_cap': 10.0,            # 最低市值过滤（亿元）
}

# ==================== 分析配置 ====================

ANALYSIS_CONFIG = {
    'top_n': 10,                       # 排行榜显示数量
    'price_bins': 20,                  # 价格分布直方图分组数
    'moving_average_periods': [5, 10, 20, 60],  # 移动平均线周期
    'rsi_period': 14,                  # RSI计算周期
}

# ==================== 网络配置 ====================

NETWORK_CONFIG = {
    'timeout': 30,                     # 请求超时时间（秒）
    'retry_times': 3,                  # 重试次数
    'retry_delay': 5,                  # 重试延迟（秒）
    'use_proxy': False,                # 是否使用代理
    'proxy_url': None,                 # 代理URL
}

# ==================== 日志配置 ====================

LOG_CONFIG = {
    'level': 'INFO',                   # 日志级别：DEBUG, INFO, WARNING, ERROR
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_max_size': 10 * 1024 * 1024, # 日志文件最大大小（10MB）
    'backup_count': 5,                 # 备份文件数量
}

# ==================== 导出配置 ====================

EXPORT_CONFIG = {
    'csv_encoding': 'utf-8-sig',       # CSV文件编码
    'excel_engine': 'openpyxl',        # Excel引擎
    'date_format': '%Y-%m-%d',         # 日期格式
    'time_format': '%H:%M:%S',         # 时间格式
}

# ==================== 功能开关 ====================

FEATURE_FLAGS = {
    'enable_realtime_monitor': True,   # 启用实时监控
    'enable_data_analysis': True,      # 启用数据分析
    'enable_alert_system': True,       # 启用预警系统
    'enable_schedule_collection': True,# 启用定时收集
    'enable_visualization': False,     # 启用数据可视化（需要matplotlib）
}

def get_config_summary():
    """获取配置摘要"""
    summary = []
    summary.append("=" * 60)
    summary.append("A股实时行情数据获取配置摘要")
    summary.append("=" * 60)
    
    summary.append(f"\n📊 数据配置:")
    summary.append(f"  • 数据保存目录: {DATA_CONFIG['data_directory']}")
    summary.append(f"  • 监控股票数量: {len(MONITOR_STOCKS)}")
    
    summary.append(f"\n⏰ 定时任务:")
    summary.append(f"  • 收集间隔: {SCHEDULE_CONFIG['collection_interval']}分钟")
    summary.append(f"  • 仅交易时间: {SCHEDULE_CONFIG['only_trading_hours']}")
    
    summary.append(f"\n⚠️ 预警配置:")
    summary.append(f"  • 价格变动阈值: {ALERT_CONFIG['price_change_threshold']}%")
    summary.append(f"  • 换手率阈值: {ALERT_CONFIG['turnover_threshold']}%")
    
    summary.append(f"\n🔧 功能开关:")
    for feature, enabled in FEATURE_FLAGS.items():
        status = "✅ 启用" if enabled else "❌ 禁用"
        summary.append(f"  • {feature}: {status}")
    
    summary.append("\n" + "=" * 60)
    return "\n".join(summary)

if __name__ == "__main__":
    print(get_config_summary())