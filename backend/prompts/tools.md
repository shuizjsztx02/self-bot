# 工具使用指南

## 工具分类

### 文件操作工具
- `read_file`: 读取文件内容
- `write_file`: 写入文件内容
- `list_directory`: 列出目录内容
- `delete_file`: 删除文件
- `copy_file`: 复制文件
- `move_file`: 移动文件

### 代码工具
- `execute_code`: 执行 Python 代码

### 系统工具
- `calculator`: 数学计算
- `current_time`: 获取当前时间
- `json_parser`: JSON 数据处理

### 搜索工具
- `tavily_search`: Tavily 搜索（高质量）
- `duckduckgo_search`: DuckDuckGo 搜索（免费）
- `serpapi_search`: SerpApi 搜索（Google 结果）

### SubAgent
- `researcher_assistant`: 研究助手，用于深度搜索和信息整合

## 使用规则

1. **选择合适的工具**
   - 文件操作 -> 文件工具
   - 数学计算 -> calculator
   - 网络搜索 -> 搜索工具或 researcher_assistant
   - 复杂研究 -> researcher_assistant

2. **参数验证**
   - 确保必填参数已提供
   - 检查参数类型和格式

3. **结果处理**
   - 解析工具返回结果
   - 向用户清晰展示结果
   - 必要时进行后续操作

4. **错误处理**
   - 捕获并报告错误
   - 提供替代方案
