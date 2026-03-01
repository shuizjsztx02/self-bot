from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, List

from app.langchain.llm import get_llm
from app.langchain.tools.search_tools import tavily_search, duckduckgo_search, serpapi_search
from app.config import settings


class ResearchInput(BaseModel):
    topic: str = Field(description="研究主题或问题")


class ResearcherAgent:
    """
    研究助手Agent
    
    职责：
    1. 执行互联网搜索
    2. 整合多个来源的信息
    3. 生成研究报告
    
    支持两种调用方式：
    1. 独立执行：通过 research() 方法
    2. 工具模式：通过 as_tool() 方法封装为工具
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, short_term_memory=None):
        self._llm = llm
        self._short_term_memory = short_term_memory
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
    ) -> str:
        """
        独立执行研究任务（带上下文）
        
        如果有对话历史，会先获取上下文，生成更精准的搜索查询
        
        Args:
            topic: 研究主题或问题
            max_iterations: 最大迭代次数
            
        Returns:
            研究结果文本
        """
        max_iterations = max_iterations or settings.RESEARCHER_MAX_ITERATIONS
        llm = self._get_llm()
        
        context = ""
        if self._short_term_memory:
            context = self._short_term_memory.get_context_summary(max_tokens=500)
        
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
        
        for iteration in range(max_iterations):
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            
            if not response.tool_calls:
                return response.content or "无法获取研究结果"
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call.get("id", "")
                
                result = await self._execute_tool(tool_name, tool_args)
                
                messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                ))
        
        return "研究超时，请稍后重试"
    
    async def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """执行工具调用"""
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
        封装为工具供其他Agent调用
        保持向后兼容
        """
        
        async def run_research(topic: str) -> str:
            return await self.research(topic)
        
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
