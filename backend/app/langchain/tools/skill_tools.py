"""
Agent 技能管理工具

让 Agent 可以：
- 搜索 ClawHub 技能市场
- 安装 / 卸载技能
- 查看已安装技能列表
- 获取热门技能推荐

SkillManager 通过 app.core.managers.get_skill_manager() 获取全局单例，
不再使用模块级全局变量，消除多 worker 竞态风险。
"""

from typing import Optional, List
from pydantic import BaseModel, Field
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


class SkillSearchInput(BaseModel):
    """技能搜索输入"""
    query: str = Field(description="搜索关键词，如 'research', 'design', 'code'")
    limit: int = Field(default=5, description="返回数量，默认5")


class SkillInstallInput(BaseModel):
    """技能安装输入"""
    slug: str = Field(description="技能标识符，如 'deep-research', 'exa'")
    version: Optional[str] = Field(default=None, description="可选：指定版本")


class SkillActionInput(BaseModel):
    """技能操作输入"""
    slug: str = Field(description="技能标识符")


def _get_manager():
    """获取 SkillManager 全局单例（通过 core.managers 中心化管理，线程安全）"""
    from app.core.managers import get_skill_manager
    return get_skill_manager()


@tool(args_schema=SkillSearchInput)
async def skill_search(query: str, limit: int = 5) -> str:
    """搜索 ClawHub 技能市场中的技能。用于发现新能力扩展、查找特定功能的技能。

    Args:
        query: 搜索关键词
        limit: 返回数量（默认5）

    Returns:
        技能列表，包含名称、描述、下载量、标签和安装状态
    """
    manager = _get_manager()
    if not manager:
        return "错误: SkillManager 未初始化"

    skills = await manager.search_remote_skills(query, limit)

    if not skills:
        return f"未找到与 '{query}' 相关的技能。尝试其他关键词。"

    output = [f"搜索 ClawHub: '{query}'\n"]

    for i, skill in enumerate(skills, 1):
        installed_mark = "✅ 已安装" if skill.installed else "⬜ 未安装"
        version_info = f" (v{skill.installed_version})" if skill.installed_version else ""

        desc = skill.description[:80] + "..." if len(skill.description) > 80 else skill.description
        tags_str = ", ".join(skill.tags[:3]) if skill.tags else "无"

        output.append(
            f"\n[{i}] {skill.name} {installed_mark}{version_info}\n"
            f"    ID: {skill.slug}\n"
            f"    描述: {desc}\n"
            f"    下载: {skill.downloads:,} | 标签: {tags_str}\n"
            f"    安装: skill_install {skill.slug}"
        )

    output.append("\n\n使用 skill_install <ID> 安装技能")

    return "\n".join(output)


@tool(args_schema=SkillInstallInput)
async def skill_install(slug: str, version: Optional[str] = None) -> str:
    """从 ClawHub 安装技能。安装后技能会自动激活，并返回完整使用指南以便立即执行任务。

    Args:
        slug: 技能标识符（如 'deep-research', 'pptx', 'docx'）
        version: 可选，指定版本号

    Returns:
        安装结果 + 技能完整使用指南，安装后可立即按指南执行用户任务
    """
    manager = _get_manager()
    if not manager:
        return "错误: SkillManager 未初始化"

    installed = manager.list_installed_from_clawhub()
    if slug in installed:
        skill_path = manager.clawhub.get_skill_path(slug) if manager.clawhub else None
        if skill_path:
            skill = await manager.loader.load(skill_path)
            if skill:
                manager.activate_skill(skill.meta.name)
                instructions = skill.instructions or "（无详细使用说明）"
                return (
                    f"✅ 技能 '{slug}' 已安装并激活。\n\n"
                    f"**立即可用的技能指南：**\n{instructions}"
                )
        return f"✅ 技能 '{slug}' 已安装。使用 skill_list 查看所有技能。"

    skill_info = await manager.clawhub.get_skill_info(slug)
    if not skill_info:
        return (
            f"❌ 未找到技能: {slug}。\n"
            f"请先使用 skill_search 搜索正确的技能 ID，然后再安装。"
        )

    logger.info(f"[skill_install] 开始安装技能: {slug}")
    skill = await manager.install_skill_from_clawhub(
        slug=slug,
        activate=True,
        version=version,
    )

    if skill:
        instructions = skill.instructions or "（无详细使用说明，请根据技能描述自行判断操作方式）"
        if len(instructions) > 2000:
            instructions = instructions[:2000] + "\n\n...（指南过长，已截断，核心步骤如上）"

        return (
            f"✅ 技能安装成功！\n"
            f"名称: {skill.meta.name}\n"
            f"版本: {skill.meta.version or 'latest'}\n"
            f"描述: {skill.meta.description}\n"
            f"状态: 已激活\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**立即可用的技能指南（请按以下说明执行用户任务）：**\n\n"
            f"{instructions}"
        )
    else:
        return (
            f"❌ 技能安装失败: {slug}\n"
            f"可能原因：网络问题、技能不存在或权限不足。\n"
            f"建议：使用 skill_search 重新搜索，或直接用现有工具完成任务。"
        )


@tool
async def skill_list() -> str:
    """列出所有已安装的技能，包括本地技能和 ClawHub 安装的技能。

    Returns:
        已安装技能列表，包含激活状态
    """
    manager = _get_manager()
    if not manager:
        return "错误: SkillManager 未初始化"

    all_skills = manager.get_all_skills()
    clawhub_slugs = manager.list_installed_from_clawhub()
    active_names = {s.meta.name for s in manager.get_active_skills()}

    output = ["📋 已安装的技能\n"]

    output.append("📁 本地技能（内置）:")
    if all_skills:
        for name, skill in all_skills.items():
            status = "✅ 激活" if name in active_names else "⬜ 未激活"
            desc = skill.meta.description[:50] + "..." if len(skill.meta.description) > 50 else skill.meta.description
            output.append(
                f"  {status} {name}\n"
                f"      {desc}"
            )
    else:
        output.append("  (无)")

    output.append("\n🌐 ClawHub 技能（动态安装）:")
    if clawhub_slugs:
        for slug in clawhub_slugs:
            skill = next(
                (s for s in all_skills.values() if s.path and slug in str(s.path)),
                None,
            )
            status = "✅ 激活" if (skill and skill.meta.name in active_names) else "⬜ 未激活"
            if skill:
                desc = skill.meta.description[:50] + "..." if len(skill.meta.description) > 50 else skill.meta.description
                output.append(
                    f"  {status} {slug}\n"
                    f"      {desc}"
                )
            else:
                output.append(f"  {status} {slug}")
    else:
        output.append("  (无)")

    output.append(f"\n📊 统计: 本地 {len(all_skills)} 个, ClawHub {len(clawhub_slugs)} 个")
    output.append("\n使用 skill_search 搜索新技能")

    return "\n".join(output)


@tool(args_schema=SkillActionInput)
async def skill_uninstall(slug: str) -> str:
    """卸载从 ClawHub 安装的技能。只能卸载从 ClawHub 安装的技能，本地内置技能无法卸载。

    Args:
        slug: 技能标识符

    Returns:
        卸载结果
    """
    manager = _get_manager()
    if not manager:
        return "错误: SkillManager 未初始化"

    clawhub_skills = manager.list_installed_from_clawhub()

    if slug not in clawhub_skills:
        source = manager.get_skill_source(slug)
        if source == "local":
            return f"❌ '{slug}' 是本地内置技能，无法卸载。"
        else:
            return f"❌ 技能 '{slug}' 未安装或不是从 ClawHub 安装的。"

    success = await manager.uninstall_skill_from_clawhub(slug)

    if success:
        return f"✅ 技能已卸载: {slug}"
    else:
        return f"❌ 卸载失败: {slug}"


@tool
async def skill_popular() -> str:
    """获取 ClawHub 热门技能推荐。

    Returns:
        热门技能列表，包含下载量和简要描述
    """
    manager = _get_manager()
    if not manager:
        return "错误: SkillManager 未初始化"

    skills = await manager.get_popular_skills(limit=10)

    if not skills:
        return "无法获取热门技能，请检查网络连接。"

    output = ["🔥 ClawHub 热门技能 TOP 10\n"]

    for i, skill in enumerate(skills, 1):
        installed_mark = "✅" if skill.installed else "⬜"
        desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
        output.append(
            f"[{i}] {installed_mark} {skill.name}\n"
            f"    下载: {skill.downloads:,}\n"
            f"    描述: {desc}\n"
            f"    安装: skill_install {skill.slug}\n"
        )

    return "\n".join(output)
