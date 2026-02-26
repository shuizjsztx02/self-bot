from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os
import json
import aiofiles
import shutil
from app.config import settings


def resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    
    if path.startswith("./") or path.startswith("../"):
        return os.path.abspath(path)
    
    workspace = settings.WORKSPACE_PATH
    if not os.path.isabs(workspace):
        from pathlib import Path
        workspace = str(Path(__file__).parent.parent.parent.parent / workspace)
    
    os.makedirs(workspace, exist_ok=True)
    
    return os.path.join(workspace, path)


class FilePathInput(BaseModel):
    path: str = Field(description="文件路径（相对路径将保存到 workspace 目录）")


class WriteFileInput(BaseModel):
    path: str = Field(description="文件路径（相对路径将保存到 workspace 目录）")
    content: str = Field(description="要写入的内容")
    mode: str = Field(default="write", description="写入模式: write 或 append")


class ListDirInput(BaseModel):
    path: str = Field(default="", description="目录路径（默认为 workspace 目录）")
    show_hidden: bool = Field(default=False, description="是否显示隐藏文件")


class DeleteInput(BaseModel):
    path: str = Field(description="要删除的文件或目录路径")
    force: bool = Field(default=False, description="是否强制删除非空目录")


class CopyMoveInput(BaseModel):
    source: str = Field(description="源路径")
    destination: str = Field(description="目标路径")


class ReadFileInput(BaseModel):
    path: str = Field(description="文件路径")
    lines: int = Field(default=100, description="读取行数限制")


@tool(args_schema=ReadFileInput)
async def read_file(path: str, lines: int = 100) -> str:
    """读取本地文件内容"""
    try:
        resolved_path = resolve_path(path)
        async with aiofiles.open(resolved_path, "r", encoding="utf-8") as f:
            content = await f.read()
            content_lines = content.split("\n")[:lines]
            if len(content.split("\n")) > lines:
                content_lines.append(f"... (已限制读取前{lines}行)")
            return "\n".join(content_lines)
    except FileNotFoundError:
        return f"错误: 文件不存在: {path}"
    except Exception as e:
        return f"读取错误: {str(e)}"


@tool(args_schema=WriteFileInput)
async def write_file(path: str, content: str, mode: str = "write") -> str:
    """写入内容到文件，如果文件不存在则创建。相对路径将保存到 workspace 目录"""
    try:
        resolved_path = resolve_path(path)
        dir_path = os.path.dirname(resolved_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        write_mode = "a" if mode == "append" else "w"
        async with aiofiles.open(resolved_path, write_mode, encoding="utf-8") as f:
            await f.write(content)
        return f"成功写入文件: {resolved_path}"
    except Exception as e:
        return f"写入错误: {str(e)}"


@tool(args_schema=ListDirInput)
async def list_directory(path: str = "", show_hidden: bool = False) -> str:
    """列出目录内容，默认列出 workspace 目录"""
    try:
        if path:
            resolved_path = resolve_path(path)
        else:
            resolved_path = resolve_path("")
        
        if not os.path.exists(resolved_path):
            return f"错误: 目录不存在: {resolved_path}"
        if not os.path.isdir(resolved_path):
            return f"错误: 不是目录: {resolved_path}"
        
        items = []
        for item in os.listdir(resolved_path):
            if not show_hidden and item.startswith("."):
                continue
            item_path = os.path.join(resolved_path, item)
            is_dir = os.path.isdir(item_path)
            size = 0 if is_dir else os.path.getsize(item_path)
            items.append({
                "name": item,
                "type": "directory" if is_dir else "file",
                "size": size,
            })
        return json.dumps(items, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"列出目录错误: {str(e)}"


@tool(args_schema=DeleteInput)
async def delete_file(path: str, force: bool = False) -> str:
    """删除文件或空目录"""
    try:
        resolved_path = resolve_path(path)
        if not os.path.exists(resolved_path):
            return f"错误: 路径不存在: {resolved_path}"
        
        if os.path.isfile(resolved_path):
            os.remove(resolved_path)
            return f"已删除文件: {resolved_path}"
        elif os.path.isdir(resolved_path):
            if force:
                shutil.rmtree(resolved_path)
                return f"已强制删除目录: {resolved_path}"
            else:
                os.rmdir(resolved_path)
                return f"已删除空目录: {resolved_path}"
        return f"错误: 未知类型: {resolved_path}"
    except Exception as e:
        return f"删除错误: {str(e)}"


@tool(args_schema=CopyMoveInput)
async def copy_file(source: str, destination: str) -> str:
    """复制文件或目录"""
    try:
        resolved_source = resolve_path(source)
        resolved_dest = resolve_path(destination)
        
        if not os.path.exists(resolved_source):
            return f"错误: 源路径不存在: {resolved_source}"
        
        dest_dir = os.path.dirname(resolved_dest)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        
        if os.path.isfile(resolved_source):
            shutil.copy2(resolved_source, resolved_dest)
        else:
            shutil.copytree(resolved_source, resolved_dest)
        return f"已复制: {resolved_source} -> {resolved_dest}"
    except Exception as e:
        return f"复制错误: {str(e)}"


@tool(args_schema=CopyMoveInput)
async def move_file(source: str, destination: str) -> str:
    """移动或重命名文件/目录"""
    try:
        resolved_source = resolve_path(source)
        resolved_dest = resolve_path(destination)
        
        if not os.path.exists(resolved_source):
            return f"错误: 源路径不存在: {resolved_source}"
        
        dest_dir = os.path.dirname(resolved_dest)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        
        shutil.move(resolved_source, resolved_dest)
        return f"已移动: {resolved_source} -> {resolved_dest}"
    except Exception as e:
        return f"移动错误: {str(e)}"
