from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import asyncio


class MemorySummarizer:
    SUMMARY_PROMPT = """请将以下对话内容压缩成简洁的摘要，保留关键信息：

{conversation}

摘要要求：
1. 保留重要的决策、约定、事实
2. 保留用户的偏好和需求
3. 省略无关的闲聊和重复内容
4. 使用简洁的中文表达

摘要："""

    def __init__(
        self,
        llm=None,
        provider: str = "deepseek",
        model: str = None,
    ):
        self._llm = llm
        self._provider = provider
        self._model = model
        self._background_tasks: List[asyncio.Task] = []
    
    @property
    def llm(self):
        if self._llm is None:
            from app.langchain.llm import get_llm
            self._llm = get_llm(self._provider, self._model)
        return self._llm
    
    def _format_messages(self, messages: List[BaseMessage]) -> str:
        lines = []
        for msg in messages:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = msg.content or ""
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    async def summarize(self, messages: List[BaseMessage]) -> str:
        if not messages:
            return ""
        
        conversation = self._format_messages(messages)
        
        prompt = ChatPromptTemplate.from_template(self.SUMMARY_PROMPT)
        chain = prompt | self.llm
        
        response = await chain.ainvoke({"conversation": conversation})
        
        return response.content
    
    async def summarize_async(self, messages: List[BaseMessage]) -> asyncio.Task:
        task = asyncio.create_task(self.summarize(messages))
        self._background_tasks.append(task)
        task.add_done_callback(lambda t: self._background_tasks.remove(t))
        return task
    
    async def assess_importance(self, content: str) -> int:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """评估以下内容的重要性，返回1-5的分数：
1 - 无关紧要的闲聊
2 - 一般信息
3 - 有一定价值的信息
4 - 重要信息，值得记住
5 - 非常重要，核心信息

只返回数字，不要其他内容。"""),
            ("human", "{content}"),
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({"content": content[:500]})
        
        try:
            score = int(response.content.strip())
            return max(1, min(5, score))
        except:
            return 3
    
    async def extract_key_info(self, content: str) -> List[str]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """从以下内容中提取关键信息点，每行一个，格式简洁。
如果没有重要信息，返回"无"。"""),
            ("human", "{content}"),
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({"content": content[:1000]})
        
        lines = response.content.strip().split("\n")
        return [line.strip() for line in lines if line.strip() and line.strip() != "无"]
