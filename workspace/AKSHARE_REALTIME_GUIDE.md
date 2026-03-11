# AKShare A股实时行情数据获取指南

## 概述

本指南介绍如何使用 AKShare 获取 A 股实时行情数据。AKShare 是一个开源的 Python 金融数据接口库，提供丰富的中国金融市场数据。

## 快速开始

### 1. 安装依赖

```bash
# 安装AKShare及相关依赖
pip install akshare pandas numpy openpyxl

# 或者使用国内镜像加速
pip install akshare pandas numpy openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 测试安装

```bash
python simple_akshare_test.py
```

### 3. 获取实时行情数据

```bash
python get_a_share_realtime_data.py
```

## 核心功能

### 1. 获取所有A股实时行情

```python
import akshare as ak

# 获取所有A股实时行情数据
realtime_data = ak.stock_zh_a_spot()

# 查看数据基本信息
print(f"股票数量: {len(realtime_data)}")
print(f"数据列数: {len(realtime_data.columns)}")
print(realtime_data.head())
```

### 2. 获取特定股票实时行情

```python
import akshare as ak

# 获取特定股票实时行情
symbols = ['000001', '600519', '000858']  # 平安银行、贵州茅台、五粮液
specific_data = ak.stock_zh_a_spot(symbol=symbols)
```

### 3. 数据字段说明

获取的实时行情数据包含以下字段：

| 字段名 | 说明 | 单位 |
|--------|------|------|
| **代码** | 股票代码 | - |
| **名称** | 股票名称 | - |
| **最新价** | 最新成交价 | 元 |
| **涨跌幅** | 涨跌幅百分比 | % |
| **涨跌额** | 涨跌金额 | 元 |
| **成交量** | 成交量 | 手 |
| **成交额** | 成交金额 | 万元 |
| **振幅** | 振幅百分比 | % |
| **最高** | 当日最高价 | 元 |
| **最低** | 当日最低价 | 元 |
| **今开** | 今日开盘价 | 元 |
| **昨收** | 昨日收盘价 | 元 |
| **量比** | 量比 | - |
| **换手率** | 换手率百分比 | % |
| **市盈率** | 市盈率 | - |
| **市净率** | 市净率 | - |
| **总市值** | 总市值 | 亿元 |
| **流通市值** | 流通市值 | 亿元 |

## 使用示例

### 示例1：获取并保存数据

```python
import akshare as ak
import pandas as pd
from datetime import datetime

# 获取实时数据
data = ak.stock_zh_a_spot()

# 保存为CSV
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_filename = f'a_share_realtime_{timestamp}.csv'
data.to_csv(csv_filename, index=False, encoding='utf-8-sig')
print(f"数据已保存到: {csv_filename}")

# 保存为Excel
excel_filename = f'a_share_realtime_{timestamp}.xlsx'
data.to_excel(excel_filename, index=False)
print(f"数据已保存到: {excel_filename}")
```

### 示例2：数据分析

```python
import akshare as ak
import pandas as pd

# 获取数据
data = ak.stock_zh_a_spot()

# 基本统计
print("=== 市场概况 ===")
print(f"上涨股票数量: {len(data[data['涨跌幅'] > 0])}")
print(f"下跌股票数量: {len(data[data['涨跌幅'] < 0])}")
print(f"平盘股票数量: {len(data[data['涨跌幅'] == 0])}")

# 涨幅榜
top_gainers = data.nlargest(10, '涨跌幅')
print("\n=== 涨幅榜TOP10 ===")
print(top_gainers[['代码', '名称', '最新价', '涨跌幅', '成交量']])

# 成交额榜
top_volume = data.nlargest(10, '成交额')
print("\n=== 成交额TOP10 ===")
print(top_volume[['代码', '名称', '最新价', '成交额', '换手率']])
```

### 示例3：监控特定股票

```python
import akshare as ak
import time
from datetime import datetime

def monitor_stocks(symbols, interval=60):
    """
    监控特定股票
    :param symbols: 股票代码列表
    :param interval: 监控间隔（秒）
    """
    while True:
        try:
            # 获取当前时间
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{current_time}] 监控更新")
            
            # 获取实时数据
            data = ak.stock_zh_a_spot(symbol=symbols)
            
            if not data.empty:
                for _, row in data.iterrows():
                    print(f"{row['代码']} {row['名称']}: {row['最新价']}元 "
                          f"({row['涨跌幅']:+.2f}%) 成交量:{row['成交量']:,}手")
            else:
                print("未获取到数据")
            
            # 等待指定间隔
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n监控已停止")
            break
        except Exception as e:
            print(f"获取数据失败: {e}")
            time.sleep(interval)

# 监控茅台、平安银行、宁德时代
monitor_stocks(['600519', '000001', '300750'], interval=30)
```

## 常见问题

### Q1: 获取的数据为空怎么办？
**可能原因：**
1. 网络连接问题
2. 不在交易时间（9:30-15:00）
3. AKShare版本过旧
4. 数据源暂时不可用

**解决方案：**
1. 检查网络连接
2. 确认是否在交易时间
3. 升级AKShare：`pip install --upgrade akshare`
4. 稍后重试

### Q2: 安装AKShare失败怎么办？
```bash
# 使用国内镜像
pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或者使用豆瓣镜像
pip install akshare -i https://pypi.douban.com/simple/
```

### Q3: 如何获取更多历史数据？
AKShare 还提供历史K线数据：
```python
# 获取历史K线数据
hist_data = ak.stock_zh_a_hist(
    symbol="600519",          # 股票代码
    period="daily",           # 日K线
    start_date="20240101",    # 开始日期
    end_date="20241231",      # 结束日期
    adjust="qfq"              # 前复权
)
```

### Q4: 数据延迟是多少？
实时行情数据通常有15-30秒的延迟，具体取决于数据源。

## 高级功能

### 1. 定时收集数据

```python
import schedule
import time
from datetime import datetime

def collect_realtime_data():
    """定时收集实时数据"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f"[{timestamp}] 开始收集数据...")
    
    try:
        data = ak.stock_zh_a_spot()
        if not data.empty:
            filename = f'data/a_share_{timestamp}.csv'
            data.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"数据已保存: {filename}")
    except Exception as e:
        print(f"收集数据失败: {e}")

# 每5分钟收集一次
schedule.every(5).minutes.do(collect_realtime_data)

while True:
    schedule.run_pending()
    time.sleep(1)
```

### 2. 数据可视化

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 绘制涨跌幅分布
plt.figure(figsize=(10, 6))
plt.hist(data['涨跌幅'], bins=50, alpha=0.7, color='blue')
plt.xlabel('涨跌幅 (%)')
plt.ylabel('股票数量')
plt.title('A股涨跌幅分布')
plt.grid(True, alpha=0.3)
plt.show()
```

## 注意事项

1. **数据用途**：获取的数据仅供学习和研究使用，不构成投资建议
2. **交易时间**：实时数据仅在交易时间（9:30-15:00）有效更新
3. **网络要求**：需要稳定的网络连接
4. **数据准确性**：数据来源于第三方，可能存在延迟或误差
5. **使用限制**：请遵守相关法律法规，不要过度频繁请求数据

## 相关资源

- [AKShare官方文档](https://akshare.akfamily.xyz/)
- [AKShare GitHub仓库](https://github.com/akfamily/akshare)
- [Pandas文档](https://pandas.pydata.org/docs/)
- [Python金融数据分析教程](https://www.runoob.com/python3/python3-tutorial.html)

## 获取帮助

如果遇到问题：
1. 查看本指南的常见问题部分
2. 运行测试脚本：`python simple_akshare_test.py`
3. 检查依赖是否安装：`pip list | grep akshare`
4. 查看AKShare官方文档

---

**最后更新：2025年3月**
**作者：智能助手**