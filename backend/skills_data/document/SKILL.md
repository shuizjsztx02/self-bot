---
name: document-creator
description: 创建和编辑各种文档格式，包括 Markdown、PDF、Word 等。适用于需要创建结构化文档的场景。
version: "1.0.0"
tags:
  - document
  - pdf
  - markdown
  - 文档
  - 报告
  - 创建
priority: 10
dependencies:
  tools:
    - write_file
    - read_file
permissions:
  allowed_tools:
    - write_file
    - read_file
    - list_directory
  forbidden_tools:
    - delete_file
    - execute_code
---

# 文档创建技能

## 概述

此技能用于创建专业的文档，支持多种格式和结构化内容。

## 工作流程

### 1. 需求分析
- 确认文档类型（报告、方案、手册、笔记等）
- 确认目标受众
- 确认必需章节

### 2. 结构规划
- 制定文档大纲
- 规划章节结构
- 确定样式规范

### 3. 内容创建
- 按章节撰写内容
- 使用 Markdown 格式
- 添加适当的标题层级

### 4. 格式规范

#### Markdown 标题层级
```markdown
# 一级标题 - 文档标题
## 二级标题 - 章节标题
### 三级标题 - 小节标题
#### 四级标题 - 段落标题
```

#### 代码块格式
使用三个反引号包裹代码，并指定语言：
```python
print("Hello, World!")
```

#### 列表格式
- 无序列表使用 `-` 或 `*`
- 有序列表使用数字 `1.`, `2.`

## 示例输出

创建一个项目报告：

```markdown
# 项目进度报告

## 项目概述
本项目旨在...

## 本周进展
### 已完成任务
- 任务1
- 任务2

### 进行中任务
- 任务3 (进度: 50%)

## 下周计划
1. 完成任务3
2. 开始任务4

## 风险与问题
暂无
```

## 注意事项

- 文件默认保存到 workspace 目录
- 使用 UTF-8 编码
- 文件名使用英文或拼音，避免特殊字符
