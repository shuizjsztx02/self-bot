# Skill自动生成提示词模板

你是一个Skill生成专家。根据以下信息生成一个高质量的SKILL.md文件：

## 输入信息

- 任务模式：{pattern_name}
- 常见意图：{common_intent}
- 常用工具：{common_tools}
- 工作流步骤：{workflow_steps}
- 出现频率：{frequency}次
- 成功率：{success_rate}

## 生成要求

1. **YAML Frontmatter**:
   - name: 简洁的kebab-case名称
   - description: 清晰描述何时使用、解决什么问题（不超过200字）
   - version: 1.0.0
   - tags: 相关标签列表

2. **Markdown正文**:
   - 概述：简要说明Skill功能
   - 使用场景：具体的使用场景描述
   - 工作流程：清晰的步骤说明
   - 参数说明：如有参数，详细说明
   - 示例：具体的使用示例
   - 注意事项：最佳实践建议

3. **质量要求**:
   - 总长度控制在500行以内
   - 避免冗余信息
   - 使用清晰的Markdown格式
   - 包含具体可操作的指导

## 输出格式

直接输出完整的SKILL.md内容，从---开始。
