#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare A股实时行情数据获取配置
"""

# 数据保存配置
DATA_CONFIG = {
    'output_dir': 'realtime_data',      # 数据保存目录
    'csv_encoding': 'utf-8-sig',        # CSV文件编码
    'excel_engine': 'openpyxl',         # Excel引擎
}

# 股票筛选配置
STOCK_FILTER = {
    'min_price': 1.0,                   # 最低价格过滤（元）
    'max_price': 10000.0,               # 最高价格过滤（元）
    'min_volume': 10000,                # 最低成交量过滤（股）
}

# 排行榜配置
RANKING_CONFIG = {
    'top_gainers_count': 20,            # 涨幅榜显示数量
    'top_volume_count': 20,             # 成交量榜显示数量
    'top_turnover_count': 20,           # 换手率榜显示数量
}

# 监控股票列表（示例）
MONITOR_STOCKS = [
    # 金融股
    '000001',  # 平安银行
    '600036',  # 招商银行
    '601318',  # 中国平安
    
    # 消费股
    '600519',  # 贵州茅台
    '000858',  # 五粮液
    '000568',  # 泸州老窖
    
    # 科技股
    '002415',  # 海康威视
    '000725',  # 京东方A
    '002475',  # 立讯精密
    
    # 医药股
    '600276',  # 恒瑞医药
    '000538',  # 云南白药
    '600196',  # 复星医药
    
    # 新能源
    '002594',  # 比亚迪
    '300750',  # 宁德时代
    '601012',  # 隆基绿能
]

# 预警配置
ALERT_CONFIG = {
    'price_change_alert': 5.0,          # 价格变动预警阈值（%）
    'volume_spike_alert': 3.0,          # 成交量突增预警倍数
    'turnover_alert': 20.0,             # 换手率预警阈值（%）
}

# 定时任务配置
SCHEDULE_CONFIG = {
    'interval_minutes': 5,              # 定时获取间隔（分钟）
    'trading_hours_only': True,         # 是否只在交易时间运行
    'trading_start': '09:30',           # 交易开始时间
    'trading_end': '15:00',             # 交易结束时间
}

# 数据源配置
DATA_SOURCE = {
    'primary': 'akshare',               # 主要数据源
    'fallback': None,                   # 备用数据源
    'timeout': 30,                      # 请求超时时间（秒）
    'retry_times': 3,                   # 重试次数
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',                    # 日志级别
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'file': 'akshare_realtime.log',     # 日志文件
}

def get_trading_hours():
    """获取交易时间配置"""
    return {
        'morning_start': '09:30',
        'morning_end': '11:30',
        'afternoon_start': '13:00',
        'afternoon_end': '15:00',
    }

def is_trading_time(current_time=None):
    """
    判断当前是否为交易时间
    
    Args:
        current_time: 当前时间，默认为当前系统时间
    
    Returns:
        bool: 是否为交易时间
    """
    from datetime import datetime
    
    if current_time is None:
        current_time = datetime.now()
    
    trading_hours = get_trading_hours()
    
    # 转换为时间字符串
    time_str = current_time.strftime('%H:%M')
    weekday = current_time.weekday()  # 0-6，周一到周日
    
    # 周末不是交易日
    if weekday >= 5:
        return False
    
    # 检查是否在交易时间段内
    morning_session = (trading_hours['morning_start'] <= time_str <= trading_hours['morning_end'])
    afternoon_session = (trading_hours['afternoon_start'] <= time_str <= trading_hours['afternoon_end'])
    
    return morning_session or afternoon_session

def get_output_filename(prefix='realtime', extension='csv'):
    """
    生成输出文件名
    
    Args:
        prefix: 文件名前缀
        extension: 文件扩展名
    
    Returns:
        str: 完整的文件名
    """
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"

if __name__ == "__main__":
    # 测试配置
    print("配置测试:")
    print(f"监控股票数量: {len(MONITOR_STOCKS)}")
    print(f"交易时间检查: {is_trading_time()}")
    print(f"输出文件名示例: {get_output_filename()}")
    print(f"数据保存目录: {DATA_CONFIG['output_dir']}")