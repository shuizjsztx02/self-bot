from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import os
import aiofiles
import json


class MemoryEntry(BaseModel):
    id: str
    content: str
    importance: int
    category: str
    tags: List[str]
    source_conversation_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MDStorage:
    def __init__(self, storage_path: str = "./data/memories"):
        self.storage_path = Path(storage_path)
        self.index_path = self.storage_path / "index.json"
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        for level in range(1, 6):
            (self.storage_path / f"level_{level}").mkdir(exist_ok=True)
    
    def _get_file_path(self, entry: MemoryEntry) -> Path:
        return self.storage_path / f"level_{entry.importance}" / f"{entry.id}.md"
    
    def _format_md_content(self, entry: MemoryEntry) -> str:
        frontmatter = {
            "id": entry.id,
            "importance": entry.importance,
            "category": entry.category,
            "tags": entry.tags,
            "source_conversation_id": entry.source_conversation_id,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        }
        
        lines = ["---"]
        lines.extend(f"{k}: {json.dumps(v)}" for k, v in frontmatter.items())
        lines.append("---")
        lines.append("")
        lines.append(entry.content)
        
        return "\n".join(lines)
    
    def _parse_md_content(self, content: str) -> tuple[dict, str]:
        lines = content.split("\n")
        
        if lines[0] != "---":
            return {}, content
        
        frontmatter = {}
        body_start = 0
        
        for i, line in enumerate(lines[1:], 1):
            if line == "---":
                body_start = i + 1
                break
            
            if ": " in line:
                key, value = line.split(": ", 1)
                try:
                    frontmatter[key] = json.loads(value)
                except:
                    frontmatter[key] = value
        
        body = "\n".join(lines[body_start:])
        
        return frontmatter, body
    
    async def save(self, entry: MemoryEntry) -> str:
        file_path = self._get_file_path(entry)
        content = self._format_md_content(entry)
        
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        
        await self._update_index(entry)
        
        return str(file_path)
    
    async def load(self, entry_id: str) -> Optional[MemoryEntry]:
        for level in range(1, 6):
            file_path = self.storage_path / f"level_{level}" / f"{entry_id}.md"
            
            if file_path.exists():
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                
                frontmatter, body = self._parse_md_content(content)
                
                return MemoryEntry(
                    id=frontmatter.get("id", entry_id),
                    content=body,
                    importance=frontmatter.get("importance", 3),
                    category=frontmatter.get("category", "general"),
                    tags=frontmatter.get("tags", []),
                    source_conversation_id=frontmatter.get("source_conversation_id"),
                    created_at=datetime.fromisoformat(frontmatter["created_at"]) if "created_at" in frontmatter else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(frontmatter["updated_at"]) if "updated_at" in frontmatter else datetime.utcnow(),
                )
        
        return None
    
    async def delete(self, entry_id: str) -> bool:
        for level in range(1, 6):
            file_path = self.storage_path / f"level_{level}" / f"{entry_id}.md"
            
            if file_path.exists():
                os.remove(file_path)
                await self._remove_from_index(entry_id)
                return True
        
        return False
    
    async def list_by_level(self, level: int) -> List[MemoryEntry]:
        entries = []
        level_path = self.storage_path / f"level_{level}"
        
        if not level_path.exists():
            return entries
        
        for file_path in level_path.glob("*.md"):
            entry = await self.load(file_path.stem)
            if entry:
                entries.append(entry)
        
        return entries
    
    async def list_all(self) -> List[MemoryEntry]:
        entries = []
        for level in range(1, 6):
            entries.extend(await self.list_by_level(level))
        return entries
    
    async def _update_index(self, entry: MemoryEntry) -> None:
        index = await self._load_index()
        
        index[entry.id] = {
            "importance": entry.importance,
            "category": entry.category,
            "tags": entry.tags,
            "created_at": entry.created_at.isoformat(),
        }
        
        await self._save_index(index)
    
    async def _remove_from_index(self, entry_id: str) -> None:
        index = await self._load_index()
        index.pop(entry_id, None)
        await self._save_index(index)
    
    async def _load_index(self) -> dict:
        if not self.index_path.exists():
            return {}
        
        async with aiofiles.open(self.index_path, "r", encoding="utf-8") as f:
            content = await f.read()
        
        return json.loads(content)
    
    async def _save_index(self, index: dict) -> None:
        async with aiofiles.open(self.index_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(index, indent=2, ensure_ascii=False))
