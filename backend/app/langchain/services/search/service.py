"""
Search 服务

执行互联网搜索，整合多个来源的信息

职责：
1. 多搜索引擎支持 - 支持 tavily, duckduckgo, serpapi
2. 对话上下文整合 - 利用对话历史理解搜索意图
3. 迭代搜索 - 支持多轮搜索优化
4. 工具封装 - 可作为工具供其他服务调用

不包含：
- Agent 概念（已移除）
- 知识库检索（由 RagService 负责）
"""
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import logging

from app.langchain.llm import get_llm
from app.langchain.tools.search_tools import tavily_search, duckduckgo_search, serpapi_search
from app.config import settings
from app.langchain.tracing.unified_tracer import (
    start_search_trace,
    end_search_trace,
    trace_step,
)

logger = logging.getLogger(__name__)


class ResearchInput(BaseModel):
    """研究输入 - 与原实现一致"""
    topic: str = Field(description="研究主题或问题")


@dataclass
class SearchServiceConfig:
    """Search 服务配置"""
    max_iterations: int = 3
    enable_context: bool = True
    max_context_tokens: int = 500
    preferred_engine: str = "tavily"


@dataclass
class SearchResult:
    """搜索结果"""
    query: str
    context: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    iterations: int = 1
    
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)
    
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "context": self.context,
            "sources": self.sources,
            "iterations": self.iterations,
        }


class SearchService:
    """
    Search 服务
    
    完整保留 ResearcherAgent 的所有功能：
    1. 多搜索引擎支持 (tavily, duckduckgo, serpapi)
    2. 对话上下文整合
    3. 迭代搜索 (max_iterations)
    4. 工具封装 (as_tool)
    
    使用方式：
        service = SearchService()
        result = await service.research("人工智能发展趋势")
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        short_term_memory=None,
        config: Optional[SearchServiceConfig] = None,
    ):
        self._llm = llm
        self._short_term_memory = short_term_memory
        self.config = config or SearchServiceConfig()
        self._tools = [tavily_search, duckduckgo_search, serpapi_search]
        self._tools_by_name = {t.name: t for t in self._tools}
    
    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = get_llm()
        return self._llm
    
    @property
    def tools(self) -> list:
        return self._tools
    
    async def research(
        self,
        topic: str,
        max_iterations: Optional[int] = None,
    ) -> SearchResult:
        """
        独立执行研究任务（带上下文）
        
        如果有对话历史，会先获取上下文，生成更精准的搜索查询
        
        Args:
            topic: 研究主题或问题
            max_iterations: 最大迭代次数
            
        Returns:
            SearchResult 实例
        """
        max_iterations = max_iterations or self.config.max_iterations
        llm = self._get_llm()
        
        ctx = start_search_trace(topic)
        
        logger.info(f"[SearchService] research start: topic='{topic[:50]}...', max_iterations={max_iterations}")
        
        context = ""
        if self._short_term_memory and self.config.enable_context:
            context = self._short_term_memory.get_context_summary(
                max_tokens=self.config.max_context_tokens
            )
        
        system_content = """你是研究助手，擅长：
1. 深度搜索：使用多种搜索引擎获取全面信息
2. 信息整合：整合多个来源的信息
3. 报告生成：生成结构化的研究报告

请使用可用的搜索工具完成研究任务，并给出综合性的回答。

注意事项：
- 优先使用 tavily_search，它提供更准确的搜索结果
- 如果一个搜索引擎失败，尝试使用其他搜索引擎
- 整合多个来源的信息，给出全面的回答"""

        if context:
            system_content += f"""

## 对话历史上下文
以下是用户之前的对话历史，请参考这些信息来更好地理解用户的研究需求：

{context}

请基于对话历史上下文来理解用户的研究主题，如果主题中包含代词（如"它"、"这个"等），请根据上下文解析其含义。"""
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=topic),
        ]
        
        llm_with_tools = llm.bind_tools(self._tools)
        
        iterations = 0
        final_content = ""
        
        try:
            with trace_step("search_execution", {"topic": topic[:100], "max_iterations": max_iterations}):
                for iteration in range(max_iterations):
                    iterations = iteration + 1
                    logger.info(f"[SearchService] Starting iteration {iterations}/{max_iterations}")
                    
                    response = await llm_with_tools.ainvoke(messages)
                    messages.append(response)
                    
                    if not response.tool_calls:
                        final_content = response.content or "无法获取研究结果"
                        logger.info(f"[SearchService] No tool calls, returning response: len={len(final_content)}")
                        break
                    
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_id = tool_call.get("id", "")
                        
                        logger.info(f"[SearchService] Executing tool: {tool_name}, args={str(tool_args)[:100]}")
                        
                        with trace_step("tool_execution", {"tool_name": tool_name, "args": str(tool_args)[:100]}):
                            result = await self._execute_tool(tool_name, tool_args)
                        
                        logger.info(f"[SearchService] Tool result: {tool_name} -> {str(result)[:200]}...")
                        
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                        ))
                else:
                    final_content = "研究超时，请稍后重试"
                    logger.warning(f"[SearchService] Max iterations reached: {max_iterations}")
            
            end_search_trace(output=final_content[:100] if final_content else None)
            
            logger.info(f"[SearchService] research complete: iterations={iterations}, result_len={len(final_content)}")
            
            return SearchResult(
                query=topic,
                context=final_content,
                sources=[],
                iterations=iterations,
            )
            
        except Exception as e:
            logger.error(f"[SearchService] Error in research: {e}")
            end_search_trace(error=str(e))
            raise
    
    async def research_stream(
        self,
        topic: str,
        max_iterations: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式版本的搜索研究
        
        Args:
            topic: 研究主题或问题
            max_iterations: 最大迭代次数
            
        Yields:
            响应片段
        """
        max_iterations = max_iterations or self.config.max_iterations
        llm = self._get_llm()
        
        ctx = start_search_trace(topic)
        
        logger.info(f"[SearchService] research_stream start: topic='{topic[:50]}...'")
        
        context = ""
        if self._short_term_memory and self.config.enable_context:
            context = self._short_term_memory.get_context_summary(
                max_tokens=self.config.max_context_tokens
            )
        
        system_content = """你是研究助手，擅长：
1. 深度搜索：使用多种搜索引擎获取全面信息
2. 信息整合：整合多个来源的信息
3. 报告生成：生成结构化的研究报告

请使用可用的搜索工具完成研究任务，并给出综合性的回答。

注意事项：
- 优先使用 tavily_search，它提供更准确的搜索结果
- 如果一个搜索引擎失败，尝试使用其他搜索引擎
- 整合多个来源的信息，给出全面的回答"""

        if context:
            system_content += f"""

## 对话历史上下文
以下是用户之前的对话历史，请参考这些信息来更好地理解用户的研究需求：

{context}

请基于对话历史上下文来理解用户的研究主题，如果主题中包含代词（如"它"、"这个"等），请根据上下文解析其含义。"""
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=topic),
        ]
        
        llm_with_tools = llm.bind_tools(self._tools)
        
        iterations = 0
        full_content = ""
        
        try:
            for iteration in range(max_iterations):
                iterations = iteration + 1
                logger.info(f"[SearchService] Stream iteration {iterations}/{max_iterations}")
                
                iteration_content = ""
                tool_calls_by_index = {}
                
                with trace_step("llm_stream", {"iteration": iterations}):
                    async for chunk in llm_with_tools.astream(messages):
                        if chunk.content:
                            iteration_content += chunk.content
                            full_content += chunk.content
                            yield {
                                "type": "content",
                                "content": chunk.content,
                            }
                        
                        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                            for tc_chunk in chunk.tool_call_chunks:
                                tc_index = tc_chunk.get("index", 0)
                                tc_id = tc_chunk.get("id")
                                
                                if tc_index not in tool_calls_by_index:
                                    tool_calls_by_index[tc_index] = {
                                        "id": tc_id or "",
                                        "name": "",
                                        "args": "",
                                    }
                                
                                if tc_id:
                                    tool_calls_by_index[tc_index]["id"] = tc_id
                                
                                if tc_chunk.get("name"):
                                    tool_calls_by_index[tc_index]["name"] += tc_chunk["name"]
                                
                                if tc_chunk.get("args"):
                                    args_str = tc_chunk["args"]
                                    if isinstance(args_str, str):
                                        tool_calls_by_index[tc_index]["args"] += args_str
                                    else:
                                        tool_calls_by_index[tc_index]["args"] += str(args_str)
                
                from langchain_core.messages import AIMessage
                ai_message = AIMessage(content=iteration_content)
                
                if tool_calls_by_index:
                    import json
                    tool_calls = []
                    for tc_index in sorted(tool_calls_by_index.keys()):
                        tc_data = tool_calls_by_index[tc_index]
                        if tc_data["name"]:
                            try:
                                args = json.loads(tc_data["args"]) if tc_data["args"] else {}
                            except:
                                args = {}
                            tool_calls.append({
                                "id": tc_data["id"] or f"call_{tc_index}",
                                "name": tc_data["name"],
                                "args": args,
                            })
                    ai_message.tool_calls = tool_calls
                
                messages.append(ai_message)
                
                if not ai_message.tool_calls:
                    logger.info(f"[SearchService] No tool calls, finalizing: content_len={len(full_content)}")
                    
                    end_search_trace(output=full_content[:100] if full_content else None)
                    
                    yield {
                        "type": "done",
                        "content": full_content,
                    }
                    return
                
                logger.info(f"[SearchService] Tool calls detected: {[tc['name'] for tc in ai_message.tool_calls]}")
                
                for tool_call in ai_message.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call.get("id", "")
                    
                    logger.info(f"[SearchService] Executing tool: {tool_name}")
                    
                    yield {
                        "type": "tool_call",
                        "name": tool_name,
                        "arguments": tool_args,
                    }
                    
                    with trace_step("tool_execution", {"tool_name": tool_name}):
                        result = await self._execute_tool(tool_name, tool_args)
                    
                    logger.info(f"[SearchService] Tool result: {tool_name} -> {str(result)[:200]}...")
                    
                    yield {
                        "type": "tool_result",
                        "name": tool_name,
                        "result": str(result)[:500],
                    }
                    
                    messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                    ))
            
            logger.warning(f"[SearchService] Max iterations reached: {max_iterations}")
            end_search_trace(error="Max iterations reached")
            
            yield {
                "type": "done",
                "content": full_content or "研究超时，请稍后重试",
            }
            
        except Exception as e:
            logger.error(f"[SearchService] Error in research_stream: {e}")
            end_search_trace(error=str(e))
            yield {
                "type": "error",
                "error": str(e),
            }
    
    async def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """执行工具调用 - 与原实现一致"""
        tool = self._tools_by_name.get(tool_name)
        if not tool:
            return f"工具 '{tool_name}' 不存在"
        
        try:
            if hasattr(tool, "ainvoke"):
                return await tool.ainvoke(tool_args)
            elif hasattr(tool, "invoke"):
                return tool.invoke(tool_args)
            elif hasattr(tool, "func"):
                import asyncio
                if asyncio.iscoroutinefunction(tool.func):
                    return await tool.func(**tool_args)
                else:
                    return tool.func(**tool_args)
            else:
                return f"工具 '{tool_name}' 无法执行"
        except Exception as e:
            return f"执行 '{tool_name}' 时出错: {str(e)}"
    
    def as_tool(self) -> StructuredTool:
        """
        封装为工具供其他服务调用
        
        与原实现完全一致
        """
        
        async def run_research(topic: str) -> str:
            result = await self.research(topic)
            return result.context
        
        return StructuredTool(
            name="researcher_assistant",
            description="""研究助手：执行深度搜索、信息整合和报告生成任务。

适用场景：
- 需要搜索互联网获取最新信息
- 需要整合多个来源的信息
- 需要生成研究报告

输入应该是研究主题或问题。""",
            args_schema=ResearchInput,
            func=lambda topic: None,
            coroutine=run_research,
        )
    
    async def quick_search(self, query: str, top_k: int = 5) -> str:
        """
        快速搜索（单次，不迭代）
        
        直接使用首选搜索引擎执行单次搜索
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            
        Returns:
            搜索结果文本
        """
        logger.info(f"[SearchService] quick_search: query='{query[:50]}...'")
        
        preferred_tool = self._tools_by_name.get(self.config.preferred_engine)
        if not preferred_tool:
            preferred_tool = self._tools[0]
        
        with trace_step("quick_search", {"query": query[:100], "engine": preferred_tool.name}):
            result = await self._execute_tool(preferred_tool.name, {"query": query})
        
        logger.info(f"[SearchService] quick_search complete: len={len(result)}")
        
        return result
