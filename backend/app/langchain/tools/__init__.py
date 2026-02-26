from .file_tools import read_file, write_file, list_directory, delete_file, copy_file, move_file
from .code_tools import execute_code
from .system_tools import calculator, current_time, json_parser
from .search_tools import tavily_search, duckduckgo_search, serpapi_search


def get_all_tools():
    return [
        read_file, write_file, list_directory, delete_file, copy_file, move_file,
        execute_code,
        calculator, current_time, json_parser,
        tavily_search, duckduckgo_search, serpapi_search,
    ]


def get_file_tools():
    return [read_file, write_file, list_directory, delete_file, copy_file, move_file]


def get_code_tools():
    return [execute_code]


def get_system_tools():
    return [calculator, current_time, json_parser]


def get_search_tools():
    return [tavily_search, duckduckgo_search, serpapi_search]


async def get_all_tools_with_mcp():
    tools = get_all_tools()
    
    try:
        from app.mcp import get_all_mcp_tools
        mcp_tools = await get_all_mcp_tools()
        tools.extend(mcp_tools)
    except Exception as e:
        print(f"Warning: Failed to load MCP tools: {e}")
    
    return tools
