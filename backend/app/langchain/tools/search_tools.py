from langchain_core.tools import tool
from pydantic import BaseModel, Field
from app.config import settings
import httpx
import json


class TavilyInput(BaseModel):
    query: str = Field(description="搜索查询内容")
    max_results: int = Field(default=5, description="返回结果数量")


class DuckDuckGoInput(BaseModel):
    query: str = Field(description="搜索查询内容")
    max_results: int = Field(default=5, description="返回结果数量")


class SerpApiInput(BaseModel):
    query: str = Field(description="搜索查询内容")
    num: int = Field(default=10, description="返回结果数量")


@tool(args_schema=TavilyInput)
async def tavily_search(query: str, max_results: int = 5) -> str:
    """使用Tavily搜索引擎搜索互联网信息，返回高质量搜索结果"""
    if not settings.TAVILY_API_KEY:
        return "错误: TAVILY_API_KEY 未配置"
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": f"Bearer {settings.TAVILY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        results = []
        if data.get("answer"):
            results.append(f"【AI答案】\n{data['answer']}\n")
        
        if data.get("results"):
            results.append("【搜索结果】")
            for i, item in enumerate(data["results"], 1):
                results.append(
                    f"\n{i}. {item.get('title', '无标题')}\n"
                    f"   URL: {item.get('url', '')}\n"
                    f"   {item.get('content', '')[:300]}..."
                )
        
        return "\n".join(results) if results else "未找到相关结果"
    except Exception as e:
        return f"搜索错误: {str(e)}"


@tool(args_schema=DuckDuckGoInput)
async def duckduckgo_search(query: str, max_results: int = 5) -> str:
    """使用DuckDuckGo搜索引擎搜索信息，免费无需API密钥"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        results = []
        if data.get("AbstractText"):
            results.append(f"【摘要】\n{data['AbstractText']}")
            if data.get("AbstractURL"):
                results.append(f"来源: {data['AbstractURL']}")
        
        if data.get("Answer"):
            results.append(f"\n【直接回答】\n{data['Answer']}")
        
        related = data.get("RelatedTopics", [])[:max_results]
        if related:
            results.append("\n【相关主题】")
            for i, topic in enumerate(related, 1):
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(f"\n{i}. {topic['Text']}")
        
        return "\n".join(results) if results else f"未找到关于 '{query}' 的相关结果"
    except Exception as e:
        return f"搜索错误: {str(e)}"


@tool(args_schema=SerpApiInput)
async def serpapi_search(query: str, num: int = 10) -> str:
    """使用SerpApi搜索Google结果"""
    if not settings.SERPAPI_API_KEY:
        return "错误: SERPAPI_API_KEY 未配置"
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": settings.SERPAPI_API_KEY,
                    "q": query,
                    "num": num,
                    "hl": "zh-cn",
                    "gl": "cn",
                },
            )
            response.raise_for_status()
            data = response.json()
        
        results = []
        
        if data.get("answer_box"):
            answer = data["answer_box"]
            results.append("【答案框】")
            if answer.get("title"):
                results.append(f"标题: {answer['title']}")
            if answer.get("answer"):
                results.append(f"答案: {answer['answer']}")
        
        organic = data.get("organic_results", [])
        if organic:
            results.append("\n【搜索结果】")
            for i, item in enumerate(organic, 1):
                results.append(
                    f"\n{i}. {item.get('title', '无标题')}\n"
                    f"   URL: {item.get('link', '')}\n"
                    f"   {item.get('snippet', '')[:200]}"
                )
        
        return "\n".join(results) if results else "未找到相关结果"
    except Exception as e:
        return f"搜索错误: {str(e)}"
