import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model


class MCPClient:
    def __init__(self, server_script: str, server_args: List[str] = None, cwd: str = None, env: dict = None, command: str = None, use_shell: bool = False, use_module: bool = False):
        self.server_script = server_script
        self.server_args = server_args or []
        self.cwd = cwd
        self.env = env
        self.command = command
        self.use_shell = use_shell
        self.use_module = use_module
        self._process = None
        self._tools: Dict[str, dict] = {}
        self._initialized = False
        self._request_id = 0
    
    async def start(self):
        if self._process:
            return
        
        process_env = dict(os.environ)
        if self.env:
            process_env.update(self.env)
        
        if self.use_shell:
            cmd_parts = [self.command, self.server_script] + self.server_args if self.command else [self.server_script] + self.server_args
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd_parts)
            
            self._process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                env=process_env,
            )
        else:
            exec_cmd = self.command if self.command else sys.executable
            
            if self.use_module:
                exec_args = ["-m", self.server_script] + self.server_args
            else:
                exec_args = [self.server_script] + self.server_args
            
            print(f"Starting MCP server: {exec_cmd} {' '.join(exec_args)}")
            
            self._process = await asyncio.create_subprocess_exec(
                exec_cmd,
                *exec_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                env=process_env,
            )
        
        await self._initialize()
        self._initialized = True
    
    async def _initialize(self):
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "self-bot",
                "version": "1.0.0"
            }
        }, timeout=60)
        
        await self._send_notification("notifications/initialized", {})
        
        tools_response = await self._send_request("tools/list", {}, timeout=30)
        self._tools = {tool["name"]: tool for tool in tools_response.get("tools", [])}
    
    async def _send_request(self, method: str, params: dict, timeout: float = 30) -> dict:
        if not self._process:
            raise RuntimeError("MCP server not started")
        
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }
        
        request_str = json.dumps(request) + "\n"
        self._process.stdin.write(request_str.encode())
        await self._process.stdin.drain()
        
        max_attempts = 100
        for _ in range(max_attempts):
            try:
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                stderr_output = ""
                if self._process.stderr:
                    try:
                        stderr_data = await asyncio.wait_for(
                            self._process.stderr.read(1024),
                            timeout=1
                        )
                        stderr_output = stderr_data.decode() if stderr_data else ""
                    except:
                        pass
                raise RuntimeError(f"MCP server timeout after {timeout}s. stderr: {stderr_output}")
            
            if not response_line:
                raise RuntimeError("No response from MCP server")
            
            line_str = response_line.decode().strip()
            
            if not line_str:
                continue
            
            try:
                response = json.loads(line_str)
                break
            except json.JSONDecodeError:
                print(f"MCP server non-JSON output: {line_str[:200]}")
                continue
        else:
            raise RuntimeError("MCP server did not return valid JSON after max attempts")
        
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        
        return response.get("result", {})
    
    async def _send_notification(self, method: str, params: dict):
        if not self._process:
            raise RuntimeError("MCP server not started")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        notification_str = json.dumps(notification) + "\n"
        self._process.stdin.write(notification_str.encode())
        await self._process.stdin.drain()
    
    async def call_tool(self, name: str, arguments: dict) -> Any:
        if not self._initialized:
            await self.start()
        
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        
        content = response.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")
        
        return response
    
    def get_tools(self) -> Dict[str, dict]:
        return self._tools
    
    async def stop(self):
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None
            self._initialized = False


class MCPToolWrapper:
    def __init__(self, client: MCPClient, tool_name: str, tool_info: dict):
        self.client = client
        self.tool_name = tool_name
        self.tool_info = tool_info
        self._schema = tool_info.get("inputSchema", {})
    
    async def __call__(self, **kwargs) -> str:
        return await self.client.call_tool(self.tool_name, kwargs)
    
    def to_langchain_tool(self) -> BaseTool:
        schema = self._schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        field_definitions = {}
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "string")
            prop_desc = prop_info.get("description", "")
            
            python_type = self._json_type_to_python(prop_type)
            
            if prop_name in required:
                field_definitions[prop_name] = (python_type, Field(description=prop_desc))
            else:
                field_definitions[prop_name] = (python_type | None, Field(default=None, description=prop_desc))
        
        args_schema = create_model(
            f"{self.tool_name}Input",
            **field_definitions
        ) if field_definitions else None
        
        async def _run(**kwargs):
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            return await self.client.call_tool(self.tool_name, filtered_kwargs)
        
        return StructuredTool(
            name=self.tool_name,
            description=self.tool_info.get("description", ""),
            args_schema=args_schema,
            coroutine=_run,
        )
    
    def _json_type_to_python(self, json_type: str):
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return type_map.get(json_type, str)


class MCPToolManager:
    _instance = None
    _clients: Dict[str, MCPClient] = {}
    _tools: Dict[str, List[BaseTool]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def register_server(
        self,
        name: str,
        server_script: str,
        server_args: List[str] = None,
        cwd: str = None,
        env: dict = None,
        command: str = None,
        use_shell: bool = False,
        use_module: bool = False,
    ):
        if name in self._clients:
            return self._tools.get(name, [])
        
        client = MCPClient(server_script, server_args, cwd, env, command, use_shell, use_module)
        await client.start()
        
        self._clients[name] = client
        
        tools = []
        for tool_name, tool_info in client.get_tools().items():
            wrapper = MCPToolWrapper(client, tool_name, tool_info)
            tools.append(wrapper.to_langchain_tool())
        
        self._tools[name] = tools
        return tools
    
    def get_tools(self, server_name: str = None) -> List[BaseTool]:
        if server_name:
            return self._tools.get(server_name, [])
        
        all_tools = []
        for tools in self._tools.values():
            all_tools.extend(tools)
        return all_tools
    
    async def stop_all(self):
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
        self._tools.clear()


async def get_word_mcp_tools() -> List[BaseTool]:
    manager = MCPToolManager()
    
    base_path = Path(__file__).parent.parent.parent / "mcp_servers" / "word"
    server_script = str(base_path / "word_mcp_server.py")
    
    if not Path(server_script).exists():
        print(f"Warning: Word MCP server not found at {server_script}")
        return []
    
    print(f"Loading Word MCP from: {server_script}")
    return await manager.register_server("word", server_script, cwd=str(base_path))


async def get_excel_mcp_tools() -> List[BaseTool]:
    manager = MCPToolManager()
    
    base_path = Path(__file__).parent.parent.parent / "mcp_servers" / "excel"
    src_path = base_path / "src"
    
    if not src_path.exists():
        print(f"Warning: Excel MCP server not found at {src_path}")
        return []
    
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src_path)
    
    print(f"Loading Excel MCP from: {src_path}")
    return await manager.register_server(
        "excel",
        server_script="excel_mcp",
        server_args=["stdio"],
        cwd=str(src_path),
        env=env,
        command=sys.executable,
        use_module=True,
    )


async def get_pptx_mcp_tools() -> List[BaseTool]:
    manager = MCPToolManager()
    
    base_path = Path(__file__).parent.parent.parent / "mcp_servers" / "pptx"
    server_script = str(base_path / "ppt_mcp_server.py")
    
    if not Path(server_script).exists():
        print(f"Warning: PPTX MCP server not found at {server_script}")
        return []
    
    print(f"Loading PPTX MCP from: {server_script}")
    return await manager.register_server("pptx", server_script, cwd=str(base_path))


async def get_notion_mcp_tools() -> List[BaseTool]:
    manager = MCPToolManager()
    
    base_path = Path(__file__).parent.parent.parent / "mcp_servers" / "notion"
    src_path = base_path / "src"
    
    if not src_path.exists():
        print(f"Warning: Notion MCP server not found at {src_path}")
        return []
    
    notion_api_key = os.getenv("NOTION_API_KEY")
    database_id = os.getenv("NOTION_DATABASE_ID")
    
    if not notion_api_key or not database_id:
        print(f"Warning: NOTION_API_KEY or NOTION_DATABASE_ID not set in environment")
        return []
    
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src_path)
    env["NOTION_API_KEY"] = notion_api_key
    env["NOTION_DATABASE_ID"] = database_id
    
    print(f"Loading Notion MCP from: {src_path}")
    return await manager.register_server(
        "notion",
        server_script="notion_mcp",
        server_args=["stdio"],
        cwd=str(src_path),
        env=env,
        command=sys.executable,
        use_module=True,
    )


async def get_all_mcp_tools() -> List[BaseTool]:
    tools = []
    
    print("\n" + "=" * 60)
    print("开始加载 MCP 工具...")
    print("=" * 60)
    
    try:
        word_tools = await get_word_mcp_tools()
        tools.extend(word_tools)
        print(f"✅ Word MCP: {len(word_tools)} 个工具")
    except Exception as e:
        import traceback
        print(f"❌ Word MCP 加载失败: {e}")
        traceback.print_exc()
    
    try:
        excel_tools = await get_excel_mcp_tools()
        tools.extend(excel_tools)
        print(f"✅ Excel MCP: {len(excel_tools)} 个工具")
    except Exception as e:
        import traceback
        print(f"❌ Excel MCP 加载失败: {e}")
        traceback.print_exc()
    
    try:
        pptx_tools = await get_pptx_mcp_tools()
        tools.extend(pptx_tools)
        print(f"✅ PPTX MCP: {len(pptx_tools)} 个工具")
    except Exception as e:
        import traceback
        print(f"❌ PPTX MCP 加载失败: {e}")
        traceback.print_exc()
    
    try:
        notion_tools = await get_notion_mcp_tools()
        tools.extend(notion_tools)
        print(f"✅ Notion MCP: {len(notion_tools)} 个工具")
    except Exception as e:
        import traceback
        print(f"❌ Notion MCP 加载失败: {e}")
        traceback.print_exc()
    
    try:
        from .feishu_client import get_feishu_mcp_tools
        feishu_tools = await get_feishu_mcp_tools()
        tools.extend(feishu_tools)
        print(f"✅ Feishu MCP: {len(feishu_tools)} 个工具")
    except Exception as e:
        import traceback
        print(f"❌ Feishu MCP 加载失败: {e}")
        traceback.print_exc()
    
    print("=" * 60)
    print(f"总计加载 {len(tools)} 个 MCP 工具")
    print("=" * 60 + "\n")
    
    return tools

