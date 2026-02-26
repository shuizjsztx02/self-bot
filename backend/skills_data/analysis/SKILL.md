---
name: skill-creator
description: 动态创建新的 Skill。当用户需要定义新的能力或工作流程时使用此技能。
version: "1.0.0"
tags:
  - skill
  - create
  - define
  - 动态
  - 创建
  - 定义
priority: 5
dependencies:
  tools:
    - write_file
permissions:
  allowed_tools:
    - write_file
    - read_file
---

# Skill 创建技能

## 概述

此技能用于动态创建新的 Skill，让 Agent 能够扩展自身能力。

## Skill 定义规范

### 文件结构
```
skills_data/
└── skill-name/
    └── SKILL.md
```

### SKILL.md 格式

```markdown
---
name: skill-name
description: 技能描述，说明何时使用此技能
version: "1.0.0"
tags:
  - tag1
  - tag2
priority: 10
dependencies:
  tools:
    - tool1
    - tool2
permissions:
  allowed_tools:
    - tool1
  forbidden_tools:
    - dangerous_tool
---

# Skill 名称

## 概述
技能的详细说明...

## 工作流程
1. 步骤1
2. 步骤2

## 示例
...
```

## 创建流程

### 1. 收集需求
询问用户需要创建什么类型的 Skill：
- 这个 Skill 的目的是什么？
- 需要使用哪些工具？
- 有什么限制或权限要求？

### 2. 设计 Skill
- 确定名称和描述
- 定义标签（用于匹配）
- 规划工作流程
- 设置权限

### 3. 生成 SKILL.md
按照规范生成文件内容。

### 4. 保存文件
使用 `write_file` 工具保存到 `skills_data/[skill-name]/SKILL.md`

## 示例对话

用户: "我需要一个专门写周报的 Skill"

Agent: 好的，我来帮你创建一个周报生成 Skill。

```markdown
---
name: weekly-report
description: 生成周报文档，汇总本周工作进展和下周计划
tags:
  - report
  - weekly
  - 周报
  - 汇报
priority: 10
---

# 周报生成技能

## 工作流程
1. 收集本周完成的任务
2. 整理遇到的问题
3. 规划下周计划
4. 生成格式化周报

## 周报模板
...
```

已创建 Skill: weekly-report

## 动态定义 Tool

在 Skill 中可以定义新的 Tool：

```markdown
## Tool: my-custom-tool

### Description
工具描述

### Parameters
```json
{
  "param1": {
    "type": "string",
    "description": "参数描述"
  }
}
```
```

## 注意事项

- Skill 名称使用小写字母和连字符
- 描述要清晰，便于匹配
- 合理设置权限，避免安全风险
- 新创建的 Skill 会自动加载
