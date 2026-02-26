from langchain_core.callbacks import BaseCallbackHandler
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import uuid


class AgentCallbackHandler(BaseCallbackHandler):
    def __init__(self, conversation_id: str = None):
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.logs: List[Dict] = []
        self.current_step = 0
        self.start_time = None
    
    def _log(self, event: str, data: Dict = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": self.conversation_id,
            "step": self.current_step,
            "event": event,
            "data": data or {},
        }
        self.logs.append(entry)
        self._print_log(entry)
    
    def _print_log(self, entry: Dict):
        event = entry["event"]
        data = entry["data"]
        
        if event == "llm_start":
            print(f"[LLM] 开始调用...")
        elif event == "llm_end":
            tokens = data.get("tokens", 0)
            print(f"[LLM] 完成 (tokens: {tokens})")
        elif event == "tool_start":
            print(f"[Tool] 调用: {data.get('name', 'unknown')}")
        elif event == "tool_end":
            print(f"[Tool] 完成: {data.get('name', 'unknown')}")
        elif event == "chain_start":
            print(f"[Chain] 开始: {data.get('name', 'unknown')}")
        elif event == "chain_end":
            print(f"[Chain] 完成")
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        self._log("llm_start", {
            "prompts_count": len(prompts),
            "model": kwargs.get("invocation_params", {}).get("model", "unknown"),
        })
    
    def on_llm_end(
        self,
        response: Any,
        **kwargs: Any,
    ) -> None:
        tokens = 0
        if hasattr(response, "llm_output") and response.llm_output:
            tokens = response.llm_output.get("token_usage", {}).get("total_tokens", 0)
        
        self._log("llm_end", {"tokens": tokens})
    
    def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        self._log("llm_error", {"error": str(error)})
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        self._log("tool_start", {
            "name": serialized.get("name", "unknown"),
            "input": input_str[:200] if input_str else "",
        })
    
    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        self._log("tool_end", {
            "name": kwargs.get("name", "unknown"),
            "output": output[:200] if output else "",
        })
    
    def on_tool_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        self._log("tool_error", {"error": str(error)})
    
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        if self.start_time is None:
            self.start_time = datetime.utcnow()
        
        self._log("chain_start", {
            "name": serialized.get("name", "unknown"),
            "inputs": str(inputs)[:200],
        })
        self.current_step += 1
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        self._log("chain_end", {
            "outputs": str(outputs)[:200],
        })
    
    def on_chain_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        self._log("chain_error", {"error": str(error)})
    
    def on_agent_action(
        self,
        action: Any,
        **kwargs: Any,
    ) -> None:
        self._log("agent_action", {
            "tool": action.tool,
            "tool_input": str(action.tool_input)[:200],
            "log": action.log[:200] if action.log else "",
        })
    
    def on_agent_finish(
        self,
        finish: Any,
        **kwargs: Any,
    ) -> None:
        self._log("agent_finish", {
            "output": str(finish.return_values)[:200] if finish.return_values else "",
        })
    
    def get_logs(self) -> List[Dict]:
        return self.logs
    
    def get_summary(self) -> Dict:
        duration = None
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        llm_calls = sum(1 for l in self.logs if l["event"] == "llm_start")
        tool_calls = sum(1 for l in self.logs if l["event"] == "tool_start")
        errors = sum(1 for l in self.logs if "error" in l["event"])
        
        return {
            "conversation_id": self.conversation_id,
            "duration_seconds": duration,
            "total_steps": self.current_step,
            "llm_calls": llm_calls,
            "tool_calls": tool_calls,
            "errors": errors,
        }
