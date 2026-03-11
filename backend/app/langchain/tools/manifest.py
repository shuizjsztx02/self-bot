"""
工具 Manifest — 本地工具注册数据声明

每条记录格式：(module_path, func_name, category, tags, dangerous)

新增工具只需在此文件追加一行，initializer 会自动动态导入并注册，
无需修改任何其他注册代码。
"""

from typing import List, Tuple

ToolManifestEntry = Tuple[str, str, str, List[str], bool]

LOCAL_TOOL_MANIFEST: List[ToolManifestEntry] = [
    # --- 文件操作工具 ---
    ("app.langchain.tools.file_tools",   "read_file",          "file",   ["io"],     False),
    ("app.langchain.tools.file_tools",   "write_file",         "file",   ["io"],     False),
    ("app.langchain.tools.file_tools",   "list_directory",     "file",   ["io"],     False),
    ("app.langchain.tools.file_tools",   "delete_file",        "file",   ["io"],     True),
    ("app.langchain.tools.file_tools",   "copy_file",          "file",   ["io"],     False),
    ("app.langchain.tools.file_tools",   "move_file",          "file",   ["io"],     False),

    # --- 代码执行工具 ---
    ("app.langchain.tools.code_tools",   "execute_code",       "code",   ["exec"],   True),

    # --- 系统工具 ---
    ("app.langchain.tools.system_tools", "calculator",         "system", ["util"],   False),
    ("app.langchain.tools.system_tools", "current_time",       "system", ["util"],   False),
    ("app.langchain.tools.system_tools", "json_parser",        "system", ["util"],   False),

    # --- 搜索工具 ---
    ("app.langchain.tools.search_tools", "tavily_search",      "search", ["web"],    False),
    ("app.langchain.tools.search_tools", "duckduckgo_search",  "search", ["web"],    False),
    ("app.langchain.tools.search_tools", "serpapi_search",     "search", ["web"],    False),

    # --- 沙箱 Shell 工具（供 Skills 使用） ---
    ("app.langchain.tools.shell_tools",  "sandbox_shell",      "shell",  ["exec", "skill"], False),
    ("app.langchain.tools.shell_tools",  "pip_install",        "shell",  ["exec", "skill"], False),
    ("app.langchain.tools.shell_tools",  "npx_run",            "shell",  ["exec", "skill"], False),

    # --- Skill 管理工具 ---
    ("app.langchain.tools.skill_tools",  "skill_search",       "skill",  ["manage"], False),
    ("app.langchain.tools.skill_tools",  "skill_install",      "skill",  ["manage"], False),
    ("app.langchain.tools.skill_tools",  "skill_list",         "skill",  ["manage"], False),
    ("app.langchain.tools.skill_tools",  "skill_uninstall",    "skill",  ["manage"], False),
    ("app.langchain.tools.skill_tools",  "skill_popular",      "skill",  ["manage"], False),
]
