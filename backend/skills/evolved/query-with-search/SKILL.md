---
name: query-with-search
description: 自动生成的Skill，用于处理query类型的任务。 主要使用search、rag等工具。 基于5次成功执行总结，成功率90.0%。
version: 1.0.0
tags: [auto-generated, query]
generated_at: 2026-03-05T22:45:56.078488
source_pattern: test_pattern
---

# Query With Search

## 概述

自动生成的Skill，用于处理query类型的任务。 主要使用search、rag等工具。 基于5次成功执行总结，成功率90.0%。

此Skill通过分析5次成功执行的任务自动生成，成功率为90.0%。

## 使用场景

- 当用户请求涉及query时自动触发
- 适用于需要使用search, rag的任务
- 历史数据显示此类任务出现频率较高（5次）

## 工作流程

1. **step_1_search**
   调用search工具
2. **step_2_rag**
   调用rag工具

## 参数说明

- `query` (string, 必需): 用户查询内容

## 示例

**典型请求示例：**
- 意图类型：query
- 常用工具：search, rag
- 成功执行5次

## 注意事项

- 确保相关工具可用且配置正确
- 此Skill基于5次成功执行总结，建议在实际使用中继续优化
- 当前成功率90.0%，可能需要人工审核关键步骤

## 元数据

- 自动生成时间：2026-03-05 22:45:56
- 源模式ID：test_pattern
- 原始任务数：5
- 平均执行时间：0ms