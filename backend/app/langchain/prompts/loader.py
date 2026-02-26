from pathlib import Path
from typing import Dict, Optional, Callable, Any
from datetime import datetime
import asyncio
from watchfiles import awatch


class PromptLoader:
    def __init__(
        self,
        prompts_dir: str = "./prompts",
        enable_hot_reload: bool = True,
    ):
        self.prompts_dir = Path(prompts_dir)
        self.enable_hot_reload = enable_hot_reload
        self._cache: Dict[str, tuple[str, float]] = {}
        self._watcher_task: Optional[asyncio.Task] = None
        self._on_change_callbacks: list[Callable] = []
    
    def on_change(self, callback: Callable):
        self._on_change_callbacks.append(callback)
    
    async def _notify_change(self, filename: str):
        for callback in self._on_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(filename)
                else:
                    callback(filename)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def _get_file_path(self, name: str) -> Path:
        if name.endswith(".md"):
            return self.prompts_dir / name
        return self.prompts_dir / f"{name}.md"
    
    async def load(self, name: str) -> str:
        file_path = self._get_file_path(name)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        current_mtime = file_path.stat().st_mtime
        
        if name in self._cache:
            cached_content, cached_mtime = self._cache[name]
            if cached_mtime == current_mtime:
                return cached_content
        
        content = file_path.read_text(encoding="utf-8")
        self._cache[name] = (content, current_mtime)
        
        return content
    
    async def load_all(self) -> Dict[str, str]:
        prompts = {}
        
        if not self.prompts_dir.exists():
            return prompts
        
        for file_path in self.prompts_dir.glob("*.md"):
            name = file_path.stem
            prompts[name] = await self.load(name)
        
        return prompts
    
    def clear_cache(self, name: Optional[str] = None):
        if name:
            self._cache.pop(name, None)
        else:
            self._cache.clear()
    
    async def start_watcher(self):
        if not self.enable_hot_reload:
            return
        
        if self._watcher_task is not None:
            return
        
        self._watcher_task = asyncio.create_task(self._watch_files())
    
    async def stop_watcher(self):
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            self._watcher_task = None
    
    async def _watch_files(self):
        try:
            async for changes in awatch(self.prompts_dir):
                for change_type, path in changes:
                    file_path = Path(path)
                    if file_path.suffix == ".md":
                        name = file_path.stem
                        self.clear_cache(name)
                        await self._notify_change(name)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"File watcher error: {e}")
    
    async def save(self, name: str, content: str) -> None:
        file_path = self._get_file_path(name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        self.clear_cache(name)
