# 工具使用指南

本文档详细说明所有可用工具的使用方法、参数和最佳实践。

---

## 工具分类概览

| 类别 | 工具数量 | 主要用途 |
|------|----------|----------|
| 📁 文件操作 | 6 | 读写、管理本地文件 |
| 💻 代码执行 | 1 | 运行 Python 代码 |
| 🔢 系统工具 | 3 | 计算、时间、JSON处理 |
| 🔍 网络搜索 | 3 | 互联网信息检索 |
| 📄 文档处理 | 54+ | Word/Excel/PPT 操作 |
| 📝 协作工具 | 23+ | Notion/飞书集成 |

---

## 📁 文件操作工具

### read_file
读取本地文件内容

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ✅ | 文件路径（相对路径基于 workspace） |
| lines | int | ❌ | 读取行数限制，默认 100 |

**示例**
```
读取 workspace/report.md 文件
path: "report.md"
lines: 50
```

**返回**
- 文件内容文本
- 超过行数限制时显示截断提示

---

### write_file
写入内容到文件

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ✅ | 文件路径 |
| content | string | ✅ | 要写入的内容 |
| mode | string | ❌ | 写入模式：write（覆盖）/ append（追加） |

**示例**
```
创建新文件
path: "notes.txt"
content: "这是我的笔记内容"
mode: "write"

追加内容
path: "notes.txt"
content: "\n新增的一行"
mode: "append"
```

**注意事项**
- 文件不存在时自动创建
- 目录不存在时自动创建
- 相对路径保存到 workspace 目录

---

### list_directory
列出目录内容

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ❌ | 目录路径，默认为 workspace |
| show_hidden | bool | ❌ | 是否显示隐藏文件，默认 false |

**返回**
```json
[
  {"name": "docs", "type": "directory", "size": 0},
  {"name": "report.md", "type": "file", "size": 1024}
]
```

---

### delete_file
删除文件或目录

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ✅ | 要删除的路径 |
| force | bool | ❌ | 是否强制删除非空目录，默认 false |

**⚠️ 警告**
- 删除操作不可逆
- force=true 会删除整个目录树
- 建议先确认用户意图

---

### copy_file / move_file
复制或移动文件

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | ✅ | 源路径 |
| destination | string | ✅ | 目标路径 |

---

## 💻 代码执行工具

### execute_code
执行 Python 代码并返回结果

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | ✅ | Python 代码 |
| timeout | int | ❌ | 超时时间（秒），默认 30 |

**使用场景**
- 数据处理和计算
- 生成图表
- 文本分析
- 算法验证

**示例**
```python
# 计算斐波那契数列
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

result = [fib(i) for i in range(10)]
print(result)
```

**⚠️ 安全限制**
- 运行在沙箱环境中
- 无法访问外部网络
- 无法操作文件系统
- 超时自动终止

---

## 🔢 系统工具

### calculator
数学计算器

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| expression | string | ✅ | 数学表达式 |

**支持**
- 基础运算：+, -, *, /, %
- 幂运算：**, sqrt
- 三角函数：sin, cos, tan
- 对数：log, ln

---

### current_time
获取当前时间

**返回**
```json
{
  "datetime": "2024-01-15 14:30:00",
  "timezone": "Asia/Shanghai",
  "timestamp": 1705298200
}
```

---

### json_parser
JSON 数据处理

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| data | string | ✅ | JSON 字符串 |
| operation | string | ❌ | 操作：parse/format/validate |

---

## 🔍 网络搜索工具

### tavily_search ⭐ 推荐
高质量 AI 搜索引擎

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | ✅ | 搜索查询 |
| max_results | int | ❌ | 结果数量，默认 5 |

**特点**
- 返回 AI 生成的答案摘要
- 结果质量高
- 适合深度研究

**返回格式**
```
【AI答案】
直接回答内容...

【搜索结果】
1. 标题
   URL: https://...
   摘要内容...
```

---

### duckduckgo_search
免费搜索，无需 API

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | ✅ | 搜索查询 |
| max_results | int | ❌ | 结果数量，默认 5 |

**特点**
- 完全免费
- 无需配置 API Key
- 适合简单查询

---

### serpapi_search
Google 搜索结果

**参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | ✅ | 搜索查询 |
| num | int | ❌ | 结果数量，默认 10 |

**特点**
- 返回 Google 搜索结果
- 支持答案框提取
- 需要配置 SERPAPI_API_KEY

---

## 📄 文档处理工具 (MCP)

### Word 文档工具
| 工具名 | 功能 |
|--------|------|
| create_document | 创建 Word 文档 |
| add_paragraph | 添加段落 |
| add_heading | 添加标题 |
| add_table | 添加表格 |
| add_image | 添加图片 |
| get_document_info | 获取文档信息 |
| convert_to_pdf | 转换为 PDF |

**典型工作流**
```
1. create_document(filename, title, author)
2. add_heading(filename, text, level)
3. add_paragraph(filename, text)
4. convert_to_pdf(filename)
```

### Excel 工具
| 工具名 | 功能 |
|--------|------|
| create_workbook | 创建工作簿 |
| add_sheet | 添加工作表 |
| write_cell | 写入单元格 |
| read_cell | 读取单元格 |
| add_chart | 添加图表 |

### PPT 工具
| 工具名 | 功能 |
|--------|------|
| create_presentation | 创建演示文稿 |
| add_slide | 添加幻灯片 |
| add_text_box | 添加文本框 |
| add_image | 添加图片 |

---

## 📝 协作工具 (MCP)

### Notion 工具
- 需要配置 `NOTION_API_KEY` 和 `NOTION_DATABASE_ID`
- 支持页面创建、更新、查询

### 飞书工具
- 需要配置 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`
- 支持文档、多维表格、消息发送

---

## 🤖 SubAgent

### researcher_assistant
研究助手，用于深度信息收集

**适用场景**
- 需要多轮搜索的复杂问题
- 信息整合和分析
- 报告生成

**调用方式**
```
自动触发：当任务需要深度研究时
手动请求：用户明确要求"深度研究"
```

---

## 工具选择决策指南

### 决策流程

```
                    用户请求
                        │
          ┌─────────────┼─────────────┐
          │             │             │
      文件操作？     网络搜索？     文档处理？
          │             │             │
    ┌─────┴─────┐  ┌────┴────┐  ┌────┴────┐
    │           │  │         │  │         │
 read_file  write_file tavily  Word/Excel/PPT
 list_dir   delete     duck    工具集
 copy/move             serpapi
```

### 最佳实践

1. **优先使用内置工具**
   - 文件操作 → file_tools
   - 计算 → calculator
   - 搜索 → tavily_search

2. **MCP 工具用于特定场景**
   - 创建 Word 报告 → Word MCP
   - 处理 Excel 数据 → Excel MCP
   - 制作演示文稿 → PPT MCP

3. **SubAgent 用于复杂任务**
   - 多步骤研究 → researcher_assistant
   - 信息整合 → researcher_assistant

---

## 错误处理

### 常见错误及处理

| 错误类型 | 原因 | 处理方式 |
|----------|------|----------|
| API Key 未配置 | 环境变量缺失 | 提示用户配置或使用替代工具 |
| 文件不存在 | 路径错误 | 检查路径，提示用户确认 |
| 超时 | 执行时间过长 | 增加超时时间或简化任务 |
| 权限不足 | 文件/目录权限 | 提示用户检查权限 |

### 重试策略

```
1. 分析错误原因
2. 尝试替代工具
3. 调整参数重试
4. 超过3次失败 → 向用户说明情况
```

---

## 安全注意事项

### 危险操作清单

❌ **禁止执行**
- 删除系统文件
- 格式化磁盘
- 修改系统配置
- 执行恶意代码

⚠️ **需要确认**
- 删除用户文件
- 覆盖已有文件
- 发送外部请求
- 访问敏感路径

### 安全检查流程

```
1. 检查操作类型
2. 验证路径是否在允许范围
3. 确认操作是否可逆
4. 必要时请求用户确认
```
