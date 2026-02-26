import os
from typing import Optional
from contextlib import contextmanager
from datetime import datetime


class LangSmithConfig:
    def __init__(self):
        self.enabled = False
        self.project_name = "self-bot"
        self.api_key = None
    
    def configure(
        self,
        api_key: Optional[str] = None,
        project_name: str = "self-bot",
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.project_name = project_name
        self.api_key = api_key
        
        if enabled and api_key:
            os.environ["LANGSMITH_API_KEY"] = api_key
            os.environ["LANGSMITH_PROJECT"] = project_name
            os.environ["LANGSMITH_TRACING"] = "true"
        else:
            os.environ["LANGSMITH_TRACING"] = "false"
    
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.api_key)


langsmith_config = LangSmithConfig()


def setup_langsmith(
    api_key: Optional[str] = None,
    project_name: str = "self-bot",
    enabled: bool = True,
):
    langsmith_config.configure(
        api_key=api_key,
        project_name=project_name,
        enabled=enabled,
    )


@contextmanager
def trace_context(name: str, run_type: str = "chain"):
    from langchain_core.tracers.context import collect_runs
    
    with collect_runs() as runs:
        start_time = datetime.utcnow()
        try:
            yield
        finally:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            print(f"[Trace] {name} completed in {duration:.2f}s")


class ExecutionTracer:
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.steps = []
        self.errors = []
    
    def start(self):
        self.start_time = datetime.utcnow()
        print(f"[Tracer] Starting: {self.name}")
    
    def step(self, step_name: str, data: dict = None):
        self.steps.append({
            "name": step_name,
            "time": datetime.utcnow().isoformat(),
            "data": data or {},
        })
        print(f"[Tracer] Step: {step_name}")
    
    def error(self, error: Exception):
        self.errors.append({
            "error": str(error),
            "type": type(error).__name__,
            "time": datetime.utcnow().isoformat(),
        })
        print(f"[Tracer] Error: {error}")
    
    def end(self):
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
        print(f"[Tracer] Completed: {self.name} ({duration:.2f}s)")
    
    def get_report(self) -> dict:
        return {
            "name": self.name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            "steps": self.steps,
            "errors": self.errors,
        }
