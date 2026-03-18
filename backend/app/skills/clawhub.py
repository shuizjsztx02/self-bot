"""
ClawHub 客户端

功能:
- 搜索 ClawHub 技能市场
- 安装/卸载技能
- 管理已安装技能
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import asyncio
import subprocess
import logging
import re
import shutil
import sys
import time
import zipfile
import io
from pathlib import Path

import yaml

# 导入全局HTTP客户端
try:
    from app.core.http_client import HTTPClientManager, get_http_client
    _HTTP_CLIENT_AVAILABLE = True
except ImportError:
    _HTTP_CLIENT_AVAILABLE = False

logger = logging.getLogger(__name__)


def _get_npx_command() -> str:
    """获取 npx 命令（Windows 兼容）"""
    if sys.platform == "win32":
        return "npx.cmd"
    return "npx"


def _check_npx_available() -> bool:
    """检查 npx 是否可用"""
    try:
        result = subprocess.run(
            [_get_npx_command(), "--version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


@dataclass
class ClawHubSkill:
    """ClawHub 技能元数据"""
    slug: str
    name: str
    description: str
    author: str = ""
    version: str = "1.0.0"
    downloads: int = 0
    tags: List[str] = field(default_factory=list)
    github_url: Optional[str] = None
    installed: bool = False
    installed_version: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "downloads": self.downloads,
            "tags": self.tags,
            "github_url": self.github_url,
            "installed": self.installed,
            "installed_version": self.installed_version,
        }


class ClawHubClient:
    """
    ClawHub 客户端

    支持两种实现方式:
    1. CLI 方式 (推荐): 调用 npx clawhub@latest 命令
    2. Mock 方式 (测试/降级): 模拟数据用于测试或 npx 不可用时
    """

    CLAWHUB_URL = "https://www.clawhub.com"
    CLAWHUB_API = "https://api.clawhub.com"
    CONVEX_DOWNLOAD_API = "https://wry-manatee-359.convex.site/api/v1/download"

    # 合法 slug 格式：仅允许字母、数字、短横线、下划线
    _VALID_SLUG_RE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

    def __init__(
        self,
        install_dir: str = "./skills/installed",
        use_cli: bool = True,
        timeout: int = 60,
        mock_mode: bool = False,
    ):
        """
        初始化 ClawHub 客户端
        
        Args:
            install_dir: 技能安装目录
            use_cli: 是否优先使用 CLI
            timeout: 命令超时时间（秒）
            mock_mode: 是否使用模拟模式（用于测试）
        """
        self.install_dir = Path(install_dir)
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.mock_mode = mock_mode
        
        self._npx_available = _check_npx_available()
        self._npx_cmd = _get_npx_command()
        
        if mock_mode or not self._npx_available:
            self.use_cli = False
            self.mock_mode = True
            logger.info("Using mock mode for ClawHub (npx not available or mock_mode=True)")
        else:
            self.use_cli = use_cli
        
        self._mock_skills: Dict[str, ClawHubSkill] = {}
        if self.mock_mode:
            self._init_mock_data()
    
    # Mock 技能内置详细使用说明，便于 LLM 安装后立即使用
    _MOCK_INSTRUCTIONS: Dict[str, str] = {
        "deep-research": """## Deep Research 技能使用指南

你现在具备深度研究能力。请按以下步骤执行研究任务：

1. **分解研究问题**：将用户的问题拆解为 3-5 个核心子问题
2. **多源搜索**：针对每个子问题，使用搜索工具（tavily_search 或 duckduckgo_search）进行搜索，至少搜索 3 次
3. **信息整合**：汇总搜索结果，去除重复信息，交叉验证关键数据
4. **撰写报告**：按以下格式输出研究报告：
   - 执行摘要（3-5句）
   - 主要发现（分点列举）
   - 详细分析（分章节展开）
   - 数据来源（附链接）
   - 结论与建议

注意：始终标注信息来源，对不确定的信息使用"据报道"等措辞。""",

        "exa": """## Exa Search 技能使用指南

你现在具备 Exa 神经网络搜索能力。使用方式：

1. 优先使用语义化查询而非关键词查询
2. 对搜索结果进行相关性排序和摘要
3. 提取最有价值的 3-5 条信息
4. 结合多次搜索结果综合回答

搜索策略：
- 学术/技术问题：使用专业术语搜索
- 新闻/事件：加上时间范围限定
- 对比分析：分别搜索各个选项后对比""",

        "docx": """## DOCX 文档处理技能使用指南

你现在具备 Word 文档处理能力。支持以下操作：

**创建文档**：
1. 规划文档结构（标题、章节、内容）
2. 使用 write_file 工具将内容写入 .docx 文件
3. 格式要求：标题用 # 标记，列表用 - 标记

**编辑文档**：
1. 先用 read_file 读取现有内容
2. 修改后用 write_file 覆盖保存

**最佳实践**：
- 文件路径使用 workspace/ 目录
- 文件名使用英文，避免特殊字符
- 重要文档先备份再编辑""",

        "notion": """## Notion 集成技能使用指南

你现在具备 Notion 工作区操作能力。支持以下功能：

1. **创建页面**：在指定工作区创建新页面
2. **更新内容**：修改现有页面的文本、数据库记录
3. **查询数据库**：从 Notion 数据库中检索信息
4. **管理任务**：创建和更新任务状态

操作前需要：
- 确认用户已提供 Notion API Token
- 确认目标 Database ID 或 Page ID

注意：所有操作都需要适当的 API 权限。""",

        "puppeteer": """## 浏览器自动化技能使用指南

你现在具备浏览器自动化能力。支持以下操作：

**网页抓取**：
1. 导航到目标 URL
2. 等待页面加载完成
3. 提取所需数据（文本、链接、图片等）
4. 处理动态内容（JavaScript 渲染）

**自动化测试**：
1. 模拟用户操作（点击、输入、滚动）
2. 截图记录状态
3. 验证页面元素

注意：
- 遵守网站 robots.txt 规则
- 添加适当延迟避免被封禁
- 处理登录验证时需用户提供凭据""",

        "github": """## GitHub 集成技能使用指南

你现在具备 GitHub 仓库管理能力。支持以下操作：

**仓库操作**：
- 查看仓库信息、文件列表
- 读取文件内容
- 创建/更新文件

**Issues & PR 管理**：
- 列出、创建、关闭 Issues
- 查看、创建 Pull Requests
- 添加评论和标签

**使用要求**：
- 需要用户提供 GitHub Personal Access Token
- Token 需要对应仓库的读写权限

操作格式：owner/repo（如 microsoft/vscode）""",

        "xlsx": """## Excel 数据处理技能使用指南

你现在具备 Excel 文件处理能力。支持：

**数据读取**：
1. 读取 .xlsx/.csv 文件内容
2. 解析多个 Sheet
3. 提取特定列/行数据

**数据处理**：
1. 数据清洗（去重、填充空值）
2. 数据计算（求和、平均、统计）
3. 数据筛选和排序

**数据导出**：
1. 生成新的 Excel 文件
2. 导出为 CSV 格式

所有文件操作在 workspace/ 目录下进行。""",

        "pptx": """## PowerPoint 制作技能使用指南

你现在具备 PPT 文件制作能力。请按以下流程操作：

**制作 PPT**：
1. 规划演示文稿结构（封面、目录、内容页、总结）
2. 每页内容精简，每页不超过 5 个要点
3. 使用 write_file 工具创建 .pptx 文件

**内容组织原则**：
- 封面：标题 + 副标题 + 日期
- 内容页：标题 + 要点列表 + 说明
- 总结页：关键结论 + 下一步行动

**设计建议**：
- 使用统一的字体和配色
- 图表优于文字，数据可视化
- 留白充足，避免文字过密""",
    }

    def _init_mock_data(self):
        """初始化模拟数据"""
        mock_data = [
            ClawHubSkill(
                slug="deep-research",
                name="Deep Research",
                description="深度研究工具，支持多源搜索和综合报告生成，适合需要深度调研的任务",
                author="openclaw",
                version="1.2.0",
                downloads=15000,
                tags=["research", "analysis", "report", "搜索", "研究", "报告"],
            ),
            ClawHubSkill(
                slug="exa",
                name="Exa Search",
                description="神经网络语义搜索，提供高质量的网络搜索结果，比传统搜索更智能",
                author="exa-labs",
                version="2.0.0",
                downloads=25000,
                tags=["search", "ai", "web", "搜索", "语义"],
            ),
            ClawHubSkill(
                slug="docx",
                name="DOCX Handler",
                description="Word 文档处理技能，支持创建、编辑和格式化 Word 文档",
                author="openclaw",
                version="1.5.0",
                downloads=10000,
                tags=["document", "word", "office", "文档", "Word"],
            ),
            ClawHubSkill(
                slug="notion",
                name="Notion Integration",
                description="与 Notion 工作区交互，支持页面创建、数据库查询和任务管理",
                author="notion-tools",
                version="1.0.0",
                downloads=8000,
                tags=["notion", "productivity", "database", "笔记", "数据库"],
            ),
            ClawHubSkill(
                slug="puppeteer",
                name="Puppeteer Browser",
                description="浏览器自动化技能，支持网页抓取、数据采集和自动化测试",
                author="puppeteer-team",
                version="3.0.0",
                downloads=30000,
                tags=["browser", "automation", "scraping", "爬虫", "自动化", "浏览器"],
            ),
            ClawHubSkill(
                slug="github",
                name="GitHub Integration",
                description="GitHub 仓库管理，支持 Issues、PR、文件操作和代码审查",
                author="github-tools",
                version="1.8.0",
                downloads=20000,
                tags=["github", "git", "repository", "代码", "版本控制"],
            ),
            ClawHubSkill(
                slug="xlsx",
                name="Excel Data Handler",
                description="Excel 数据处理技能，支持读取、分析、计算和生成 Excel/CSV 文件",
                author="openclaw",
                version="1.3.0",
                downloads=12000,
                tags=["excel", "xlsx", "csv", "data", "表格", "数据分析"],
            ),
            ClawHubSkill(
                slug="pptx",
                name="PowerPoint Maker",
                description="PPT 制作技能，帮助创建结构清晰、内容丰富的演示文稿",
                author="openclaw",
                version="1.1.0",
                downloads=9000,
                tags=["pptx", "powerpoint", "presentation", "演示", "幻灯片", "PPT"],
            ),
        ]

        for skill in mock_data:
            self._mock_skills[skill.slug] = skill
    
    async def close(self):
        """关闭客户端"""
        pass

    # ------------------------------------------------------------------
    # 安全工具方法
    # ------------------------------------------------------------------

    def _validate_slug(self, slug: str) -> bool:
        """验证 slug 格式，防止路径遍历和命令注入"""
        return bool(self._VALID_SLUG_RE.match(slug))

    def _safe_skill_path(self, slug: str) -> Optional[Path]:
        """安全地构建技能路径，防止路径遍历攻击"""
        if not self._validate_slug(slug):
            logger.warning(f"[ClawHub] 非法 slug 格式被拒绝: {slug!r}")
            return None

        skill_path = (self.install_dir / slug).resolve()
        install_dir_resolved = self.install_dir.resolve()

        if not str(skill_path).startswith(str(install_dir_resolved)):
            logger.warning(f"[ClawHub] 路径遍历攻击检测，已拒绝: {slug!r}")
            return None

        return skill_path

    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[ClawHubSkill]:
        """
        搜索 ClawHub 技能
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            技能列表
        """
        if self.mock_mode:
            return await self._search_mock(query, limit)
        elif self.use_cli:
            return await self._search_via_cli(query, limit)
        else:
            return []
    
    async def _search_mock(
        self,
        query: str,
        limit: int
    ) -> List[ClawHubSkill]:
        """模拟搜索（基于关键词分词匹配，支持中英文混合查询）"""
        if not query:
            # 无查询词时返回热门排序
            results = sorted(self._mock_skills.values(), key=lambda x: x.downloads, reverse=True)
            return [self._make_skill_copy(s) for s in results[:limit]]

        # 分词：将查询拆分为独立词汇（按空格、标点分割）
        tokens = re.split(r'[\s，。！？,\.!?\-_]+', query.lower())
        tokens = [t for t in tokens if len(t) >= 2]  # 过滤单字符

        if not tokens:
            tokens = [query.lower()]

        scored = []
        for skill in self._mock_skills.values():
            score = 0
            searchable = " ".join([
                skill.slug.lower(),
                skill.name.lower(),
                skill.description.lower(),
                " ".join(t.lower() for t in skill.tags),
            ])

            for token in tokens:
                if token in searchable:
                    score += 1

            if score > 0:
                scored.append((score, skill))

        # 按匹配分数降序，同分按下载量降序
        scored.sort(key=lambda x: (x[0], x[1].downloads), reverse=True)
        return [self._make_skill_copy(s) for _, s in scored[:limit]]

    def _make_skill_copy(self, skill: "ClawHubSkill") -> "ClawHubSkill":
        """创建技能的副本（附加安装状态）"""
        return ClawHubSkill(
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            author=skill.author,
            version=skill.version,
            downloads=skill.downloads,
            tags=skill.tags.copy(),
            installed=self._is_installed(skill.slug),
            installed_version=self.get_installed_version(skill.slug),
        )
    
    async def _search_via_cli(
        self,
        query: str,
        limit: int
    ) -> List[ClawHubSkill]:
        """通过 CLI 搜索（使用参数列表形式，防止 Shell 注入）"""
        try:
            proc = await asyncio.create_subprocess_exec(
                self._npx_cmd, "clawhub@latest", "search", query,
                "--no-input",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace") if stderr else ""

            if proc.returncode == 0:
                results = self._parse_search_output(output, limit)
                if results:
                    logger.info(f"[ClawHub] CLI 搜索成功，找到 {len(results)} 个技能")
                    return results
                # 解析结果为空但命令成功，可能是格式问题
                logger.warning(f"[ClawHub] CLI 搜索返回空结果，原始输出: {output[:200]}")
                return []
            else:
                if self._is_rate_limited(err_output + output):
                    logger.warning("[ClawHub] 搜索速率限制，降级到 Mock 模式")
                else:
                    logger.warning(f"[ClawHub] CLI 搜索失败: {err_output[:200]}")
                self.mock_mode = True
                self._init_mock_data()
                return await self._search_mock(query, limit)
                
        except asyncio.TimeoutError:
            logger.error("[ClawHub] CLI 搜索超时，降级到 Mock 模式")
            self.mock_mode = True
            self._init_mock_data()
            return await self._search_mock(query, limit)
        except FileNotFoundError:
            logger.error("[ClawHub] npx 未找到，请安装 Node.js，降级到 Mock 模式")
            self.mock_mode = True
            self._init_mock_data()
            return await self._search_mock(query, limit)
        except Exception as e:
            logger.error(f"[ClawHub] CLI 搜索异常: {e}，降级到 Mock 模式")
            self.mock_mode = True
            self._init_mock_data()
            return await self._search_mock(query, limit)
    
    def _parse_search_output(
        self,
        output: str,
        limit: int
    ) -> List[ClawHubSkill]:
        """解析 CLI 搜索输出
        
        实际 CLI 输出格式（clawhub@latest v0.7.0）:
            - Searching
            notion  Notion  (3.764)
            notion-skill  Notion  (3.658)
        
        每行: <slug>  <name/description>  (<score>)
        状态行（如 "- Searching"）以非字母开头，应跳过。
        """
        skills = []
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过状态行（以 -、×、✓、空格等非字母字符开头）
            if not re.match(r'^[a-zA-Z]', line):
                continue
            
            # 格式 1（新版）: slug  Name Text  (score)
            # 两个或更多空格作为分隔符
            new_fmt = re.match(
                r'^([a-zA-Z0-9_-]+)\s{2,}(.+?)\s{2,}\(([0-9.]+)\)\s*$',
                line
            )
            if new_fmt:
                slug = new_fmt.group(1)
                name_or_desc = new_fmt.group(2).strip()
                # score 是相关性得分（越高越好），不是下载量
                score_val = float(new_fmt.group(3))
                skills.append(ClawHubSkill(
                    slug=slug,
                    name=name_or_desc,
                    description=name_or_desc,
                    downloads=int(score_val * 1000),  # 用得分换算为伪下载量便于排序
                    installed=self._is_installed(slug)
                ))
                if len(skills) >= limit:
                    break
                continue
            
            # 格式 2（旧版兼容）: ● slug – description (downloads: N)
            old_fmt = re.match(
                r'[●\-]\s*(\S+)\s*[-–]\s*(.+?)(?:\s*\(downloads:\s*(\d+)\))?$',
                line
            )
            if old_fmt:
                slug = old_fmt.group(1)
                description = old_fmt.group(2).strip()
                downloads = int(old_fmt.group(3)) if old_fmt.group(3) else 0
                skills.append(ClawHubSkill(
                    slug=slug,
                    name=slug.replace('-', ' ').title(),
                    description=description,
                    downloads=downloads,
                    installed=self._is_installed(slug)
                ))
                if len(skills) >= limit:
                    break
        
        return skills
    
    # 速率限制关键词列表
    _RATE_LIMIT_KEYWORDS = [
        "rate limit exceeded",
        "rate limit",
        "too many requests",
        "429",
    ]

    def _is_rate_limited(self, output: str) -> bool:
        """检测输出中是否包含速率限制错误"""
        lower = output.lower()
        return any(kw in lower for kw in self._RATE_LIMIT_KEYWORDS)

    async def _run_cli_with_retry(
        self,
        cmd_args: list,
        cwd: str = None,
        max_retries: int = 3,
        base_delay: float = 5.0,
        timeout_multiplier: float = 2.0,
    ) -> tuple[int, str, str]:
        """
        执行 CLI 命令，遇到速率限制时自动重试（指数退避）

        Returns:
            (returncode, stdout, stderr)
        """
        for attempt in range(max_retries):
            try:
                kwargs = dict(
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                if cwd:
                    kwargs["cwd"] = cwd

                proc = await asyncio.create_subprocess_exec(*cmd_args, **kwargs)
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout * timeout_multiplier,
                )
                out_str = stdout.decode("utf-8", errors="replace")
                err_str = stderr.decode("utf-8", errors="replace") if stderr else ""

                if proc.returncode != 0 and self._is_rate_limited(err_str + out_str):
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"[ClawHub] 速率限制，第 {attempt + 1}/{max_retries} 次重试，"
                        f"{delay:.0f}s 后重试..."
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        continue

                return proc.returncode, out_str, err_str

            except asyncio.TimeoutError:
                logger.warning(f"[ClawHub] 命令超时 (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay)
                    continue
                return -1, "", "Timeout"
            except FileNotFoundError:
                return -2, "", "npx not found"
            except Exception as e:
                logger.error(f"[ClawHub] CLI 执行异常: {e}")
                return -3, "", str(e)

        return -1, "", "Max retries exceeded"

    async def install(
        self,
        slug: str,
        target_dir: str = None,
        version: str = None
    ) -> bool:
        """
        安装技能（多通道降级策略）

        安装优先级:
        1. Convex API 直接下载 ZIP（无速率限制，推荐）
        2. CLI 安装（clawhub install，可能被限流）
        3. HTTP 降级（registry URL 尝试）

        Args:
            slug: 技能标识符
            target_dir: 安装目录（默认使用 self.install_dir）
            version: 指定版本（可选）
        
        Returns:
            是否成功
        """
        if not self._validate_slug(slug):
            logger.warning(f"[ClawHub] 拒绝安装非法 slug: {slug!r}")
            return False

        if self.mock_mode:
            return await self._install_mock(slug, version)

        target = Path(target_dir) if target_dir else self.install_dir
        target.mkdir(parents=True, exist_ok=True)

        # 通道 1：Convex API 直接下载 ZIP（最快、无限流）
        logger.info(f"[ClawHub] 开始安装技能: {slug}（优先 Convex API）")
        convex_ok = await self._install_via_convex(slug, target)
        if convex_ok:
            return True

        # 通道 2：CLI 安装（可能被限流，带重试）
        logger.info(f"[ClawHub] Convex API 未成功，尝试 CLI 安装: {slug}")
        workdir = str(target.parent)
        skills_dir = target.name

        cmd_args = [
            self._npx_cmd, "clawhub@latest", "install", slug,
            "--workdir", workdir,
            "--dir", skills_dir,
            "--no-input",
        ]
        if version:
            cmd_args.append(f"--version={version}")

        returncode, out_str, err_str = await self._run_cli_with_retry(
            cmd_args, max_retries=2, base_delay=5.0
        )

        if returncode == 0:
            skill_file = target / slug / "SKILL.md"
            if skill_file.exists():
                logger.info(f"[ClawHub] CLI 安装成功: {slug} -> {skill_file}")
                return True
            installed = self._find_installed_skill(slug, target)
            if installed:
                logger.info(f"[ClawHub] 在 {installed} 找到技能文件")
                return True
            logger.error(f"[ClawHub] CLI 报告成功但文件未找到: {skill_file}")
            return False
        elif returncode == -2:
            logger.warning("[ClawHub] npx 未找到")
        else:
            combined = err_str + out_str
            if self._is_rate_limited(combined):
                logger.warning(f"[ClawHub] CLI 安装 {slug} 被速率限制")
            else:
                logger.warning(f"[ClawHub] CLI 安装失败: {(err_str or out_str)[:200]}")

        # 通道 3：HTTP 降级
        logger.info(f"[ClawHub] 所有主要通道未成功，尝试 HTTP 降级: {slug}")
        return await self._install_via_http(slug, target, version)

    def _find_installed_skill(self, slug: str, base_dir: Path) -> Optional[Path]:
        """在目录下查找技能文件（处理 slug 大小写/格式差异）"""
        if not base_dir.exists():
            return None
        for d in base_dir.iterdir():
            if d.is_dir() and slug.lower() in d.name.lower():
                skill_file = d / "SKILL.md"
                if skill_file.exists():
                    return skill_file
        return None

    async def _install_via_convex(
        self,
        slug: str,
        target: Path,
    ) -> bool:
        """
        通过 Convex API 直接下载技能 ZIP 并解压安装。
        
        这是最快且无速率限制的安装方式。
        下载 URL: https://wry-manatee-359.convex.site/api/v1/download?slug=<slug>
        返回 ZIP 包，包含 SKILL.md 及其他文件。
        """
        if not _HTTP_CLIENT_AVAILABLE:
            logger.debug("[ClawHub] HTTP客户端未初始化，跳过 Convex 下载")
            return False

        url = f"{self.CONVEX_DOWNLOAD_API}?slug={slug}"
        headers = {"User-Agent": "clawhub-selfbot/1.0"}

        try:
            # 使用全局HTTP连接池
            client = await get_http_client()
            logger.info(f"[ClawHub] Convex API 下载: {url}")
            resp = await client.get(url, headers=headers)

            if resp.status_code == 404:
                logger.info(f"[ClawHub] Convex API: 技能 {slug} 不存在 (404)")
                return False

            if resp.status_code != 200:
                logger.warning(
                    f"[ClawHub] Convex API 返回 {resp.status_code}: "
                    f"{resp.text[:200]}"
                )
                return False

            content_type = resp.headers.get("content-type", "")
            if "zip" not in content_type and resp.content[:4] != b"PK\x03\x04":
                logger.warning(
                    f"[ClawHub] Convex API 返回非 ZIP 内容: {content_type}"
                )
                return False

                # 解压 ZIP
                skill_dir = target / slug
                skill_dir.mkdir(parents=True, exist_ok=True)

                z = zipfile.ZipFile(io.BytesIO(resp.content))
                file_names = z.namelist()
                has_skill_md = any(
                    n.upper().endswith("SKILL.MD") for n in file_names
                )
                if not has_skill_md:
                    logger.warning(
                        f"[ClawHub] ZIP 中未找到 SKILL.md: {file_names}"
                    )
                    return False

                for name in file_names:
                    # 安全检查：防止路径遍历
                    if ".." in name or name.startswith("/"):
                        logger.warning(f"[ClawHub] 跳过可疑路径: {name}")
                        continue
                    
                    file_data = z.read(name)
                    out_path = skill_dir / name
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(file_data)

                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    file_size = skill_file.stat().st_size
                    logger.info(
                        f"[ClawHub] Convex API 安装成功: {slug} -> {skill_file} "
                        f"({file_size} bytes, {len(file_names)} files)"
                    )
                    return True
                else:
                    logger.warning(f"[ClawHub] 解压后未找到 SKILL.md: {skill_dir}")
                    return False

        except httpx.RequestError as e:
            logger.warning(f"[ClawHub] Convex API 网络错误: {e}")
            return False
        except zipfile.BadZipFile:
            logger.warning(f"[ClawHub] Convex API 返回的不是有效 ZIP")
            return False
        except Exception as e:
            logger.error(f"[ClawHub] Convex API 安装异常: {e}")
            return False

    async def _install_via_http(
        self,
        slug: str,
        target: Path,
        version: str = None,
    ) -> bool:
        """
        HTTP 降级安装：当 CLI 被速率限制时，直接从 ClawHub 网站获取 SKILL.md 内容。
        
        ClawHub 技能页 URL 格式: https://clawhub.ai/<author>/<slug>
        原始 SKILL.md 通常在 registry API: https://registry.clawhub.ai/skills/<slug>/SKILL.md
        也可尝试常见 GitHub 镜像路径。
        """
        if not _HTTPX_AVAILABLE:
            logger.error("[ClawHub] httpx 未安装，无法使用 HTTP 降级。运行: pip install httpx")
            return False

        # 候选 URL（按优先级排列）
        candidate_urls = [
            # ClawHub registry API
            f"https://registry.clawhub.ai/skills/{slug}/SKILL.md",
            f"https://registry.clawhub.ai/skills/{slug}/skill.md",
            # ClawHub 官网（raw 内容）
            f"https://clawhub.ai/api/skills/{slug}/raw",
        ]

        headers = {"User-Agent": "clawhub-selfbot/1.0 (self-bot integration)"}

        try:
            # 使用全局HTTP连接池
            client = await get_http_client()
            
            for url in candidate_urls:
                try:
                    logger.info(f"[ClawHub] HTTP 降级尝试: {url}")
                    resp = await client.get(url, headers=headers)
                    
                    if resp.status_code == 200 and resp.text.strip():
                        content = resp.text
                        # 写入 SKILL.md
                        skill_dir = target / slug
                        skill_dir.mkdir(parents=True, exist_ok=True)
                        skill_file = skill_dir / "SKILL.md"
                        skill_file.write_text(content, encoding="utf-8")
                        logger.info(
                            f"[ClawHub] HTTP 降级安装成功: {slug} -> {skill_file}"
                        )
                        return True
                    else:
                        logger.debug(
                            f"[ClawHub] HTTP {resp.status_code} from {url}"
                        )
                except Exception as e:
                    logger.debug(f"[ClawHub] HTTP 请求失败 {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"[ClawHub] HTTP 降级异常: {e}")

        logger.error(f"[ClawHub] HTTP 降级安装失败，所有候选 URL 均不可用: {slug}")
        return False
    
    _MOCK_DEPENDENCIES: Dict[str, Dict[str, Any]] = {
        "deep-research": {
            "pip": ["tavily-python>=0.3.0"],
            "tools": ["tavily_search"],
        },
        "exa": {
            "pip": ["exa-py>=1.0.0"],
            "env": ["EXA_API_KEY"],
            "tools": ["exa_search"],
        },
        "docx": {
            "pip": ["python-docx>=0.8.11"],
            "tools": ["read_file", "write_file"],
        },
        "notion": {
            "pip": ["notion-client>=2.0.0", "httpx"],
            "mcp_servers": [
                {
                    "name": "notion",
                    "module": "notion_mcp",
                    "command": "python -m notion_mcp stdio",
                    "env": ["NOTION_API_KEY"],
                }
            ],
            "tools": ["notion_create_page", "notion_query_database"],
            "env": ["NOTION_API_KEY"],
        },
        "puppeteer": {
            "npm": ["puppeteer"],
            "mcp_servers": [
                {
                    "name": "puppeteer",
                    "module": "puppeteer_mcp",
                    "command": "npx @anthropic/puppeteer-mcp stdio",
                }
            ],
            "tools": ["puppeteer_navigate", "puppeteer_screenshot"],
        },
        "github": {
            "pip": ["pygithub>=2.0.0"],
            "mcp_servers": [
                {
                    "name": "github",
                    "module": "github_mcp",
                    "command": "npx @modelcontextprotocol/server-github stdio",
                    "env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
                }
            ],
            "env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            "tools": ["github_list_issues", "github_create_issue"],
        },
        "xlsx": {
            "pip": ["openpyxl>=3.1.0", "pandas"],
            "tools": ["read_file", "write_file"],
        },
        "pptx": {
            "pip": ["python-pptx>=0.6.21"],
            "tools": ["read_file", "write_file"],
        },
    }

    async def _install_mock(self, slug: str, version: str = None) -> bool:
        """模拟安装（含完整使用说明和依赖声明，使 LLM 安装后可立即执行任务）"""
        if slug not in self._mock_skills:
            logger.warning(f"[ClawHub] Mock 中不存在技能: {slug}")
            return False

        skill_dir = self._safe_skill_path(slug)
        if skill_dir is None:
            return False

        skill = self._mock_skills[slug]
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        instructions = self._MOCK_INSTRUCTIONS.get(slug, f"""## {skill.name} 使用说明

{skill.description}

### 使用步骤
1. 理解用户的具体需求
2. 根据任务类型选择合适的工具组合
3. 分步骤执行，每步完成后验证结果
4. 整合所有结果并向用户展示

### 注意事项
- 遇到问题时先尝试替代方案
- 保持结果的准确性和完整性
""")

        deps = self._MOCK_DEPENDENCIES.get(slug, {})

        frontmatter: Dict[str, Any] = {
            "name": skill.name,
            "description": skill.description,
            "version": version or skill.version,
            "author": skill.author,
            "tags": skill.tags,
            "source": "clawhub",
        }
        if deps:
            frontmatter["dependencies"] = deps

        frontmatter_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)

        content = f"---\n{frontmatter_str}---\n\n{instructions}\n"

        try:
            skill_file.write_text(content, encoding='utf-8')
            logger.info(f"[ClawHub] Mock 技能安装成功: {slug} -> {skill_file}")
            return True
        except Exception as e:
            logger.error(f"[ClawHub] Mock 安装失败: {e}")
            return False
    
    async def uninstall(self, slug: str) -> bool:
        """
        卸载技能（含路径遍历防护）

        Args:
            slug: 技能标识符

        Returns:
            是否成功
        """
        skill_dir = self._safe_skill_path(slug)
        if skill_dir is None:
            return False

        if not skill_dir.exists():
            logger.warning(f"[ClawHub] 技能未安装: {slug}")
            return False

        try:
            shutil.rmtree(skill_dir)
            logger.info(f"[ClawHub] 技能卸载成功: {slug}")
            return True
        except Exception as e:
            logger.error(f"[ClawHub] 卸载失败: {e}")
            return False
    
    async def update(
        self,
        slug: str = None,
        all_skills: bool = False
    ) -> Dict[str, bool]:
        """
        更新技能
        
        Args:
            slug: 技能标识符（更新单个）
            all_skills: 是否更新所有
        
        Returns:
            更新结果 {slug: success}
        """
        results = {}
        
        if self.mock_mode:
            if all_skills:
                for installed_slug in self.list_installed():
                    results[installed_slug] = True
            elif slug:
                results[slug] = slug in self.list_installed()
            return results
        
        try:
            # 使用参数列表形式，防止 Shell 注入
            cmd_args = [self._npx_cmd, "clawhub@latest", "update"]
            if all_skills:
                cmd_args.append("--all")
            elif slug:
                if not self._validate_slug(slug):
                    logger.warning(f"[ClawHub] 拒绝更新非法 slug: {slug!r}")
                    return results
                cmd_args.append(slug)
            else:
                return results

            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=str(self.install_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout * 3
            )
            
            if proc.returncode == 0:
                if all_skills:
                    for skill in self.list_installed():
                        results[skill] = True
                else:
                    results[slug] = True
            
        except asyncio.TimeoutError:
            logger.error("Update timeout")
            if slug:
                results[slug] = False
        except FileNotFoundError:
            logger.error("npx not found")
        except Exception as e:
            logger.error(f"Update error: {e}")
            if slug:
                results[slug] = False
        
        return results
    
    async def get_popular(self, limit: int = 10) -> List[ClawHubSkill]:
        """获取热门技能"""
        if self.mock_mode:
            results = sorted(
                self._mock_skills.values(),
                key=lambda x: x.downloads,
                reverse=True
            )[:limit]
            
            return [
                ClawHubSkill(
                    slug=skill.slug,
                    name=skill.name,
                    description=skill.description,
                    author=skill.author,
                    version=skill.version,
                    downloads=skill.downloads,
                    tags=skill.tags.copy(),
                    installed=self._is_installed(skill.slug),
                    installed_version=self.get_installed_version(skill.slug),
                )
                for skill in results
            ]
        
        try:
            # 使用参数列表形式，防止 Shell 注入
            proc = await asyncio.create_subprocess_exec(
                self._npx_cmd, "clawhub@latest", "popular",
                "--limit", str(int(limit)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            if proc.returncode == 0:
                return self._parse_search_output(stdout.decode(), limit)
            else:
                logger.warning(f"CLI popular failed: {stderr.decode()}")
                self.mock_mode = True
                self._init_mock_data()
                return await self.get_popular(limit)
                
        except Exception as e:
            logger.warning(f"get_popular error: {e}")
            self.mock_mode = True
            self._init_mock_data()
            return await self.get_popular(limit)
    
    async def get_skill_info(self, slug: str) -> Optional[ClawHubSkill]:
        """获取技能详情"""
        if self.mock_mode:
            skill = self._mock_skills.get(slug)
            if skill:
                return ClawHubSkill(
                    slug=skill.slug,
                    name=skill.name,
                    description=skill.description,
                    author=skill.author,
                    version=skill.version,
                    downloads=skill.downloads,
                    tags=skill.tags.copy(),
                    installed=self._is_installed(slug),
                    installed_version=self.get_installed_version(slug),
                )
            return None
        
        skills = await self.search(slug, limit=1)
        if skills and skills[0].slug == slug:
            return skills[0]
        return None
    
    def list_installed(self) -> List[str]:
        """列出已安装的技能"""
        installed = []
        
        if self.install_dir.exists():
            for skill_dir in self.install_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        installed.append(skill_dir.name)
        
        return installed
    
    def _is_installed(self, slug: str) -> bool:
        """检查技能是否已安装"""
        return (self.install_dir / slug / "SKILL.md").exists()
    
    def get_installed_version(self, slug: str) -> Optional[str]:
        """获取已安装技能的版本"""
        skill_file = self.install_dir / slug / "SKILL.md"
        
        if not skill_file.exists():
            return None
        
        try:
            content = skill_file.read_text(encoding='utf-8')
            
            match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if match:
                frontmatter = yaml.safe_load(match.group(1))
                return frontmatter.get('version')
        except Exception:
            pass
        
        return None
    
    def get_skill_path(self, slug: str) -> Optional[Path]:
        """获取已安装技能的路径（含路径安全检查）"""
        skill_dir = self._safe_skill_path(slug)
        if skill_dir is None:
            return None
        skill_path = skill_dir / "SKILL.md"
        return skill_path if skill_path.exists() else None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        installed = self.list_installed()
        return {
            "installed_count": len(installed),
            "installed_skills": installed,
            "install_dir": str(self.install_dir),
            "mock_mode": self.mock_mode,
        }
