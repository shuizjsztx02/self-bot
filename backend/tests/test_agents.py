"""
MainAgent 和 RagAgent 服务测试脚本

测试内容：
1. MainAgent 基本对话功能
2. RagAgent 工具封装功能
3. ResearcherAgent 独立执行功能
4. 意图分类器
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def test_main_agent_basic():
    """
    测试 MainAgent 基本对话功能
    """
    console.print(Panel.fit("🧪 测试 MainAgent 基本对话功能", style="bold blue"))
    
    from app.langchain.agents.main_agent import MainAgent
    
    agent = MainAgent(
        provider="deepseek",
        user_name="测试用户",
        agent_name="智能助手",
    )
    
    test_messages = [
        "你好，请介绍一下你自己",
    ]
    
    for msg in test_messages:
        console.print(f"\n[bold green]用户:[/bold green] {msg}")
        
        try:
            result = await agent.chat(msg)
            
            if isinstance(result, dict):
                output = result.get("output", str(result))
            else:
                output = str(result)
            
            console.print(f"[bold yellow]助手:[/bold yellow] {output[:500]}...")
            
            return True
            
        except Exception as e:
            console.print(f"[bold red]错误:[/bold red] {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_main_agent_stream():
    """
    测试 MainAgent 流式对话功能
    """
    console.print(Panel.fit("🧪 测试 MainAgent 流式对话功能", style="bold blue"))
    
    from app.langchain.agents.main_agent import MainAgent
    
    agent = MainAgent(
        provider="deepseek",
        user_name="测试用户",
        agent_name="智能助手",
    )
    
    msg = "请用简短的话介绍一下Python编程语言"
    console.print(f"\n[bold green]用户:[/bold green] {msg}")
    console.print("[bold yellow]助手:[/bold yellow] ", end="")
    
    try:
        full_content = ""
        async for chunk in agent.chat_stream(msg):
            if chunk.get("type") == "token":
                content = chunk.get("content", "")
                console.print(content, end="")
                full_content += content
            elif chunk.get("type") == "done":
                console.print("\n")
                return True
        
        return False
        
    except Exception as e:
        console.print(f"\n[bold red]错误:[/bold red] {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_rag_agent_tool():
    """
    测试 RagAgent 工具封装
    """
    console.print(Panel.fit("🧪 测试 RagAgent 工具封装", style="bold blue"))
    
    from app.langchain.agents.rag_agent import RagAgent
    
    agent = RagAgent(user_id="test_user")
    
    try:
        rag_tool = agent.as_tool()
        
        console.print(f"[bold cyan]工具名称:[/bold cyan] {rag_tool.name}")
        console.print(f"[bold cyan]工具描述:[/bold cyan] {rag_tool.description[:200]}...")
        
        return True
        
    except Exception as e:
        console.print(f"[bold red]错误:[/bold red] {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_researcher_agent():
    """
    测试 ResearcherAgent 独立执行
    """
    console.print(Panel.fit("🧪 测试 ResearcherAgent 独立执行", style="bold blue"))
    
    from app.langchain.agents.researcher_agent import ResearcherAgent
    
    agent = ResearcherAgent()
    
    console.print(f"\n[bold green]测试主题:[/bold green] Python编程语言的发展历史")
    
    try:
        result = await agent.research("Python编程语言是谁发明的？")
        
        console.print(f"[bold yellow]研究结果:[/bold yellow] {result[:500]}...")
        
        return True
        
    except Exception as e:
        console.print(f"[bold red]错误:[/bold red] {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_intent_classifier():
    """
    测试意图分类器
    """
    console.print(Panel.fit("🧪 测试意图分类器", style="bold blue"))
    
    from app.langchain.routers.intent_classifier import IntentClassifier, QueryIntent
    from app.langchain.llm import get_llm
    
    llm = get_llm("deepseek")
    classifier = IntentClassifier(llm)
    
    test_queries = [
        "你好",
        "帮我写一个Python爬虫",
        "搜索一下今天的新闻",
        "公司的报销流程是什么？",
    ]
    
    passed = 0
    for query in test_queries:
        try:
            result = await classifier.classify(query)
            console.print(f"\n[bold cyan]查询:[/bold cyan] {query}")
            console.print(f"  意图: {result.intent.value}")
            console.print(f"  置信度: {result.confidence:.2f}")
            console.print(f"  理由: {result.reasoning}")
            passed += 1
        except Exception as e:
            console.print(f"[bold red]错误:[/bold red] {str(e)}")
    
    return passed == len(test_queries)


async def test_main_agent_with_tool():
    """
    测试 MainAgent 使用额外工具
    """
    console.print(Panel.fit("🧪 测试 MainAgent 工具调用", style="bold blue"))
    
    from app.langchain.agents.main_agent import MainAgent
    from app.langchain.agents.rag_agent import RagAgent
    
    
    agent = MainAgent(
        provider="deepseek",
        user_name="测试用户",
        agent_name="智能助手",
    )
    
    rag_agent = RagAgent(user_id="test_user")
    rag_tool = rag_agent.as_tool()
    
    agent.set_extra_tools([rag_tool])
    
    tools = agent.tools
    tool_names = [t.name for t in tools]
    
    console.print(f"[bold cyan]当前工具数量:[/bold cyan] {len(tools)}")
    console.print(f"[bold cyan]工具列表:[/bold cyan] {tool_names[:5]}...")
    
    has_rag_tool = "rag_search" in tool_names
    console.print(f"[bold cyan]包含RAG工具:[/bold cyan] {has_rag_tool}")
    
    return has_rag_tool


async def run_all_tests():
    """
    运行所有测试
    """
    console.print(Panel.fit(
        "[bold]🚀 开始运行 Agent 服务测试[/bold]",
        style="bold magenta",
    ))
    
    console.print("\n测试内容:")
    console.print("1. MainAgent 基本对话")
    console.print("2. MainAgent 流式对话")
    console.print("3. RagAgent 工具封装")
    console.print("4. ResearcherAgent 独立执行")
    console.print("5. 意图分类器")
    console.print("6. MainAgent 工具调用")
    
    tests = [
        ("MainAgent 基本对话", test_main_agent_basic),
        ("MainAgent 流式对话", test_main_agent_stream),
        ("RagAgent 工具封装", test_rag_agent_tool),
        ("ResearcherAgent", test_researcher_agent),
        ("意图分类器", test_intent_classifier),
        ("MainAgent 工具调用", test_main_agent_with_tool),
    ]
    
    results = []
    
    for name, test_func in tests:
        console.print(f"\n{'='*60}")
        console.print(f"[bold blue]运行测试: {name}[/bold blue]")
        console.print('='*60)
        
        try:
            success = await test_func()
            results.append((name, "✅ 通过" if success else "❌ 失败", None))
        except Exception as e:
            results.append((name, "❌ 失败", str(e)))
            console.print(f"[bold red]测试失败: {str(e)}[/bold red]")
    
    console.print("\n")
    console.print(Panel.fit(
        "[bold]📊 测试结果汇总[/bold]",
        style="bold green",
    ))
    
    table = Table(title="")
    table.add_column("测试名称", style="cyan")
    table.add_column("状态", style="bold")
    table.add_column("备注", style="yellow")
    
    for name, status, error in results:
        table.add_row(name, status, error[:50] if error else "-")
    
    console.print(table)
    
    passed = sum(1 for _, status, _ in results if "✅" in status)
    total = len(results)
    
    console.print(f"\n[bold green]通过: {passed}/{total}[/bold green]")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
