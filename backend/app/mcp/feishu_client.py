import asyncio
import os
import sys
import platform
from typing import List, Optional
from pathlib import Path

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, create_model


_feishu_session: Optional[ClientSession] = None
_feishu_tools: List[BaseTool] = []
_feishu_context_manager = None
_feishu_read = None
_feishu_write = None


async def start_feishu_mcp_session() -> ClientSession:
    global _feishu_session, _feishu_context_manager, _feishu_read, _feishu_write
    
    if _feishu_session is not None:
        try:
            if _feishu_read is not None and _feishu_write is not None:
                return _feishu_session
        except Exception:
            pass
        await stop_feishu_mcp_session()
    
    feishu_app_id = os.getenv("FEISHU_APP_ID")
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not feishu_app_id or not feishu_app_secret:
        raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set in environment")
    
    npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"
    
    safe_cache_dir = Path(__file__).parent.parent.parent / ".mcp_cache"
    safe_cache_dir.mkdir(parents=True, exist_ok=True)
    
    env = os.environ.copy()
    env["HOME"] = str(safe_cache_dir)
    env["USERPROFILE"] = str(safe_cache_dir)
    
    server_params = StdioServerParameters(
        command=npx_cmd,
        args=[
            "-y", "@larksuiteoapi/lark-mcp", "mcp",
            "-a", feishu_app_id,
            "-s", feishu_app_secret,
            "-l", "zh",
            "-m", "stdio"
        ],
        env=env
    )
    
    print(f"Starting Feishu MCP with: {npx_cmd} -y @larksuiteoapi/lark-mcp mcp -a {feishu_app_id[:10]}... -s *** -l zh -m stdio")
    
    _feishu_context_manager = stdio_client(server_params)
    _feishu_read, _feishu_write = await _feishu_context_manager.__aenter__()
    
    _feishu_session = ClientSession(_feishu_read, _feishu_write)
    await _feishu_session.__aenter__()
    await _feishu_session.initialize()
    
    print("✅ Feishu MCP session initialized")
    return _feishu_session


async def stop_feishu_mcp_session():
    global _feishu_session, _feishu_context_manager, _feishu_read, _feishu_write
    
    if _feishu_session is not None:
        try:
            await _feishu_session.__aexit__(None, None, None)
        except:
            pass
        _feishu_session = None
    
    if _feishu_context_manager is not None:
        try:
            await _feishu_context_manager.__aexit__(None, None, None)
        except:
            pass
        _feishu_context_manager = None
    
    _feishu_read = None
    _feishu_write = None
    
    print("Feishu MCP session stopped")


async def get_feishu_mcp_tools() -> List[BaseTool]:
    global _feishu_tools
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            session = await start_feishu_mcp_session()
            
            tools_response = await session.list_tools()
            mcp_tools = tools_response.tools
            
            _feishu_tools = []
            
            for mcp_tool in mcp_tools:
                tool = _convert_mcp_tool_to_langchain(session, mcp_tool)
                _feishu_tools.append(tool)
            
            print(f"Loaded {len(_feishu_tools)} Feishu MCP tools")
            return _feishu_tools
            
        except Exception as e:
            print(f"Feishu MCP attempt {attempt + 1} failed: {e}")
            await stop_feishu_mcp_session()
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                raise


def _convert_mcp_tool_to_langchain(session: ClientSession, mcp_tool) -> BaseTool:
    tool_name = mcp_tool.name
    tool_description = mcp_tool.description or ""
    
    input_schema = mcp_tool.inputSchema or {}
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    
    field_definitions = {}
    for prop_name, prop_info in properties.items():
        prop_type = prop_info.get("type", "string")
        prop_desc = prop_info.get("description", "")
        
        python_type = _json_type_to_python(prop_type)
        
        if prop_name in required:
            field_definitions[prop_name] = (python_type, Field(description=prop_desc))
        else:
            from typing import Optional
            field_definitions[prop_name] = (Optional[python_type], Field(default=None, description=prop_desc))
    
    args_schema = create_model(
        f"{tool_name}Input",
        **field_definitions
    ) if field_definitions else None
    
    async def _run(**kwargs):
        result = await session.call_tool(tool_name, arguments=kwargs)
        if hasattr(result, "content") and result.content:
            content = result.content
            if isinstance(content, list) and len(content) > 0:
                first_content = content[0]
                if hasattr(first_content, "text"):
                    return first_content.text
                return str(first_content)
        return str(result)
    
    return StructuredTool(
        name=tool_name,
        description=tool_description,
        args_schema=args_schema,
        coroutine=_run,
    )


def _json_type_to_python(json_type: str):
    from typing import Optional
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(json_type, str)


async def call_feishu_tool(tool_name: str, arguments: dict) -> str:
    session = await start_feishu_mcp_session()
    result = await session.call_tool(tool_name, arguments=arguments)
    
    if hasattr(result, "content") and result.content:
        content = result.content
        if isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if hasattr(first_content, "text"):
                return first_content.text
            return str(first_content)
    return str(result)
