# AKShare A股实时行情数据获取工具

基于AKShare库的A股实时行情数据获取工具，支持获取所有A股上市公司的实时行情数据。

## 📋 功能特性

- ✅ **实时行情获取**：获取所有A股实时行情数据
- ✅ **指定股票查询**：查询特定股票的实时行情
- ✅ **排行榜功能**：涨幅榜、成交量榜、换手率榜
- ✅ **市场概览**：上涨/下跌股票统计、涨停/跌停统计
- ✅ **数据导出**：支持CSV、Excel格式导出
- ✅ **数据摘要**：自动生成数据统计报告

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行测试脚本

```bash
python test_akshare_realtime.py
```

### 3. 运行主程序

```bash
python get_a_share_realtime_data.py
```

## 📊 数据字段说明

获取的实时行情数据包含以下字段：

| 字段名 | 说明 | 单位 |
|--------|------|------|
| **代码** | 股票代码 | - |
| **名称** | 股票名称 | - |
| **最新价** | 最新成交价 | 元 |
| **涨跌幅** | 涨跌百分比 | % |
| **涨跌额** | 涨跌金额 | 元 |
| **成交量** | 成交量 | 股 |
| **成交额** | 成交金额 | 元 |
| **振幅** | 振幅百分比 | % |
| **最高** | 当日最高价 | 元 |
| **最低** | 当日最低价 | 元 |
| **今开** | 今日开盘价 | 元 |
| **昨收** | 昨日收盘价 | 元 |
| **量比** | 量比 | - |
| **换手率** | 换手率 | % |
| **市盈率-动态** | 动态市盈率 | - |
| **市净率** | 市净率 | - |
| **总市值** | 总市值 | 元 |
| **流通市值** | 流通市值 | 元 |

## 🔧 使用方法

### 基本使用

```python
import akshare as ak

# 获取所有A股实时行情数据
realtime_data = ak.stock_zh_a_spot()

# 查看数据基本信息
print(f"股票数量: {len(realtime_data)}")
print(f"数据列数: {len(realtime_data.columns)}")
print(realtime_data.head())
```

### 获取指定股票

```python
# 指定股票代码列表
target_stocks = ['000001', '600519', '000858']

# 获取所有数据后筛选
all_data = ak.stock_zh_a_spot()
filtered_data = all_data[all_data['代码'].isin(target_stocks)]
```

### 数据排序

```python
# 按涨跌幅排序（涨幅最高）
top_gainers = realtime_data.sort_values('涨跌幅', ascending=False).head(10)

# 按成交量排序
top_volume = realtime_data.sort_values('成交量', ascending=False).head(10)

# 按换手率排序
top_turnover = realtime_data.sort_values('换手率', ascending=False).head(10)
```

## 📁 生成的文件

运行程序后会生成以下文件：

1. **CSV文件**：`a_share_realtime_YYYYMMDD_HHMMSS.csv`
   - 包含所有股票的完整实时数据

2. **Excel文件**：`a_share_realtime_YYYYMMDD_HHMMSS.xlsx`
   - Excel格式的数据文件

3. **摘要文件**：`a_share_realtime_summary_YYYYMMDD_HHMMSS.txt`
   - 数据统计摘要报告

## 🎯 高级功能

### 市场概览分析

```python
# 上涨/下跌股票统计
rising_stocks = len(data[data['涨跌幅'] > 0])
falling_stocks = len(data[data['涨跌幅'] < 0])

# 涨停/跌停股票统计
limit_up = len(data[data['涨跌幅'] >= 9.9])
limit_down = len(data[data['涨跌幅'] <= -9.9])

# 总成交额
total_turnover = data['成交额'].sum()
```

### 数据可视化（可选）

```python
import matplotlib.pyplot as plt

# 绘制涨跌幅分布直方图
plt.figure(figsize=(10, 6))
plt.hist(data['涨跌幅'], bins=50, alpha=0.7)
plt.title('A股涨跌幅分布')
plt.xlabel('涨跌幅 (%)')
plt.ylabel('股票数量')
plt.grid(True, alpha=0.3)
plt.show()
```

## ⚠️ 注意事项

1. **交易时间**：实时数据仅在交易时间（9:30-15:00）更新
2. **网络连接**：需要稳定的网络连接
3. **数据延迟**：实时数据可能有15-30秒延迟
4. **数据源限制**：AKShare依赖第三方数据源，可能偶尔不可用

## 🔍 故障排除

### 常见问题

1. **AKShare导入失败**
   ```bash
   # 使用国内镜像安装
   pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

2. **获取数据为空**
   - 检查网络连接
   - 确认是否在交易时间
   - 尝试更新AKShare版本

3. **数据列名不匹配**
   - 检查AKShare版本
   - 查看实际获取的数据列名

### 错误处理

```python
try:
    data = ak.stock_zh_a_spot()
    if data.empty:
        print("获取到的数据为空，请检查网络或数据源")
except Exception as e:
    print(f"获取数据时出错: {e}")
```

## 📈 扩展功能建议

1. **定时获取**：使用schedule库定时获取数据
2. **数据存储**：将数据保存到数据库（SQLite/MySQL）
3. **实时监控**：监控特定股票的实时变化
4. **预警系统**：设置价格/涨跌幅预警
5. **历史对比**：与历史数据对比分析

## 📚 相关资源

- [AKShare官方文档](https://akshare.akfamily.xyz/)
- [AKShare GitHub仓库](https://github.com/akfamily/akshare)
- [Pandas文档](https://pandas.pydata.org/docs/)
- [NumPy文档](https://numpy.org/doc/)

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 支持

如有问题，请：
1. 查看本文档的故障排除部分
2. 检查AKShare官方文档
3. 提交GitHub Issue