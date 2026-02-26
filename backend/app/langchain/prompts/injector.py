from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import re


class VariableInjector:
    VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')
    
    def __init__(self):
        self._providers: Dict[str, Callable[[], Any]] = {}
        self._static_vars: Dict[str, Any] = {}
    
    def register_provider(self, name: str, provider: Callable[[], Any]):
        self._providers[name] = provider
    
    def register_static(self, name: str, value: Any):
        self._static_vars[name] = value
    
    def register_batch(self, variables: Dict[str, Any]):
        self._static_vars.update(variables)
    
    def _get_value(self, name: str) -> Any:
        if name in self._static_vars:
            return self._static_vars[name]
        
        if name in self._providers:
            try:
                return self._providers[name]()
            except Exception as e:
                return f"[Error: {e}]"
        
        return f"[Unknown variable: {name}]"
    
    def inject(self, template: str) -> str:
        def replace(match):
            var_name = match.group(1)
            value = self._get_value(var_name)
            return str(value) if value is not None else ""
        
        return self.VARIABLE_PATTERN.sub(replace, template)
    
    def inject_with_vars(self, template: str, variables: Dict[str, Any]) -> str:
        original = self._static_vars.copy()
        self._static_vars.update(variables)
        result = self.inject(template)
        self._static_vars = original
        return result
    
    def extract_variables(self, template: str) -> List[str]:
        return list(set(self.VARIABLE_PATTERN.findall(template)))


class PromptContext:
    def __init__(self, injector: VariableInjector):
        self.injector = injector
        self._setup_default_providers()
    
    def _setup_default_providers(self):
        self.injector.register_provider("current_time", self._get_current_time)
        self.injector.register_provider("date", self._get_date)
        self.injector.register_provider("timestamp", self._get_timestamp)
    
    def _get_current_time(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _get_date(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_timestamp(self) -> str:
        return str(int(datetime.now().timestamp()))
    
    def set_user_info(self, user_name: str = "用户"):
        self.injector.register_static("user_name", user_name)
    
    def set_agent_info(self, agent_name: str = "智能助手"):
        self.injector.register_static("agent_name", agent_name)
    
    def set_memory_context(self, context: str):
        self.injector.register_static("memory_context", context or "暂无相关记忆")
    
    def set_short_term_summary(self, summary: str):
        self.injector.register_static("short_term_summary", summary or "暂无对话摘要")
    
    def set_token_usage(self, usage: str):
        self.injector.register_static("token_usage", usage)
    
    def set_available_tools(self, tools: str):
        self.injector.register_static("available_tools", tools)
    
    def set_conversation_id(self, conv_id: str):
        self.injector.register_static("conversation_id", conv_id)
    
    def build(
        self,
        agent_template: str,
        soul_template: str,
        tools_template: str = "",
    ) -> str:
        parts = []
        
        if soul_template:
            parts.append(self.injector.inject(soul_template))
        
        if agent_template:
            parts.append(self.injector.inject(agent_template))
        
        if tools_template:
            parts.append(self.injector.inject(tools_template))
        
        return "\n\n".join(parts)
