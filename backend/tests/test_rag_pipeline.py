"""
RagAgent 完整Pipeline测试脚本

测试流程：
1. 创建测试知识库
2. 上传测试文档
3. 文档解析与分块
4. 向量嵌入与存储
5. 知识库检索
6. RAG增强对话
"""

import asyncio
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


async def test_knowledge_base_creation():
    """
    测试知识库创建
    """
    console.print(Panel.fit("📁 测试知识库创建", style="bold blue"))
    
    from app.knowledge_base.services import KnowledgeBaseService
    from app.knowledge_base.schemas import KnowledgeBaseCreate
    from app.db.session import get_db
    
    async for db in get_db():
        kb_service = KnowledgeBaseService(db)
        
        kb_data = KnowledgeBaseCreate(
            name="测试知识库",
            description="用于测试RagAgent Pipeline的知识库",
            embedding_model="BAAI/bge-base-zh-v1.5",
            chunk_size=500,
            chunk_overlap=50,
        )
        
        try:
            kb = await kb_service.create(kb_data, owner_id="test_user")
            
            console.print(f"[bold green]✅ 知识库创建成功[/bold green]")
            console.print(f"  ID: {kb.id}")
            console.print(f"  名称: {kb.name}")
            console.print(f"  嵌入模型: {kb.embedding_model}")
            console.print(f"  分块大小: {kb.chunk_size}")
            
            return kb.id, db, kb_service
            
        except Exception as e:
            console.print(f"[bold red]❌ 知识库创建失败: {str(e)}[/bold red]")
            import traceback
            traceback.print_exc()
            return None, db, None


async def test_document_parsing():
    """
    测试文档解析
    """
    console.print(Panel.fit("📄 测试文档解析", style="bold blue"))
    
    from app.knowledge_base.parsers import ParserRouter
    
    parser_router = ParserRouter()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = Path(tmpdir) / "test.md"
        md_content = """# 测试文档

## 第一章 介绍

这是一个测试文档，用于测试RagAgent的文档解析功能。

### 1.1 背景

知识库系统是企业信息化建设的重要组成部分。它可以帮助企业：
- 整合分散的知识资源
- 提高知识复用效率
- 降低知识传递成本

### 1.2 目标

本系统的目标是构建一个高效、易用的知识管理平台。

## 第二章 技术架构

系统采用以下技术栈：
1. 后端：Python + FastAPI
2. 向量数据库：ChromaDB
3. 嵌入模型：BAAI/bge-base-zh-v1.5

### 2.1 核心模块

- 文档解析模块
- 向量嵌入模块
- 检索模块
- RAG增强模块

## 第三章 使用说明

### 3.1 文档上传

用户可以通过API上传文档，支持以下格式：
- Markdown (.md)
- PDF (.pdf)
- Word (.docx)
- Excel (.xlsx)
- PowerPoint (.pptx)

### 3.2 知识检索

系统支持语义检索，用户可以输入自然语言查询。
"""
        md_file.write_text(md_content, encoding="utf-8")
        
        txt_file = Path(tmpdir) / "test.txt"
        txt_content = """
公司报销流程说明

一、报销范围
员工因公产生的以下费用可以申请报销：
1. 交通费用
2. 住宿费用
3. 餐饮费用
4. 办公用品费用

二、报销流程
1. 填写报销申请单
2. 附上原始发票
3. 提交部门主管审批
4. 财务部门审核
5. 报销款项发放

三、注意事项
- 发票必须真实有效
- 报销金额超过5000元需要总经理审批
- 报销期限为费用发生后30天内
"""
        txt_file.write_text(txt_content, encoding="utf-8")
        
        results = {}
        
        console.print("\n[bold cyan]解析 Markdown 文档...[/bold cyan]")
        try:
            md_doc = await parser_router.parse(str(md_file))
            console.print(f"  内容长度: {len(md_doc.content)} 字符")
            console.print(f"  章节数量: {len(md_doc.sections) if md_doc.sections else 0}")
            console.print(f"  元数据: {md_doc.doc_metadata}")
            results["md"] = md_doc
        except Exception as e:
            console.print(f"  [red]解析失败: {str(e)}[/red]")
        
        console.print("\n[bold cyan]解析 TXT 文档...[/bold cyan]")
        try:
            txt_doc = await parser_router.parse(str(txt_file))
            console.print(f"  内容长度: {len(txt_doc.content)} 字符")
            console.print(f"  元数据: {txt_doc.doc_metadata}")
            results["txt"] = txt_doc
        except Exception as e:
            console.print(f"  [red]解析失败: {str(e)}[/red]")
        
        console.print(f"\n[bold green]✅ 文档解析测试完成[/bold green]")
        
        return results, tmpdir


async def test_chunking(parsed_docs):
    """
    测试文档分块
    """
    console.print(Panel.fit("✂️ 测试文档分块", style="bold blue"))
    
    from app.knowledge_base.parsers import ParserRouter
    
    parser_router = ParserRouter()
    
    all_chunks = []
    
    for doc_type, parsed_doc in parsed_docs.items():
        console.print(f"\n[bold cyan]分块 {doc_type} 文档...[/bold cyan]")
        
        try:
            chunks = parser_router.chunk_parsed_document(parsed_doc, chunk_size=300, overlap=50)
            
            console.print(f"  分块数量: {len(chunks)}")
            
            for i, chunk in enumerate(chunks[:3]):
                console.print(f"\n  [bold]分块 {i+1}:[/bold]")
                console.print(f"    内容预览: {chunk.content[:100]}...")
                console.print(f"    Token数: {chunk.token_count}")
                if chunk.page_number:
                    console.print(f"    页码: {chunk.page_number}")
                if chunk.section_title:
                    console.print(f"    章节: {chunk.section_title}")
            
            all_chunks.extend([(doc_type, chunk) for chunk in chunks])
            
        except Exception as e:
            console.print(f"  [red]分块失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
    
    console.print(f"\n[bold green]✅ 文档分块测试完成，共 {len(all_chunks)} 个分块[/bold green]")
    
    return all_chunks


async def test_embedding(chunks):
    """
    测试向量嵌入
    """
    console.print(Panel.fit("🔢 测试向量嵌入", style="bold blue"))
    
    from app.knowledge_base.services.embedding import EmbeddingService
    
    embedding_service = EmbeddingService()
    
    console.print(f"\n[bold cyan]嵌入模型: {embedding_service.model_name}[/bold cyan]")
    console.print(f"[bold cyan]嵌入维度: {embedding_service.get_embedding_dim()}[/bold cyan]")
    
    test_texts = [chunk[1].content for chunk in chunks[:5]]
    
    console.print(f"\n[bold cyan]正在嵌入 {len(test_texts)} 个文本...[/bold cyan]")
    
    try:
        embeddings = await embedding_service.embed_texts(test_texts)
        
        console.print(f"[bold green]✅ 嵌入成功[/bold green]")
        console.print(f"  嵌入数量: {len(embeddings)}")
        console.print(f"  嵌入维度: {len(embeddings[0]) if embeddings else 0}")
        
        return embeddings
        
    except Exception as e:
        console.print(f"[bold red]❌ 嵌入失败: {str(e)}[/bold red]")
        import traceback
        traceback.print_exc()
        return None


async def test_vector_store(kb_id, chunks, embeddings):
    """
    测试向量存储
    """
    console.print(Panel.fit("💾 测试向量存储", style="bold blue"))
    
    from app.knowledge_base.vector_store import VectorStoreFactory
    from app.knowledge_base.services.embedding import EmbeddingService
    import uuid
    
    vector_store = VectorStoreFactory.create("chroma")
    embedding_service = EmbeddingService()
    
    collection_name = f"kb_{kb_id.replace('-', '_')}"
    
    console.print(f"\n[bold cyan]创建向量集合: {collection_name}[/bold cyan]")
    
    try:
        await vector_store.create_collection(collection_name)
        console.print("[bold green]✅ 向量集合创建成功[/bold green]")
    except Exception as e:
        console.print(f"[yellow]集合可能已存在: {str(e)}[/yellow]")
    
    console.print(f"\n[bold cyan]插入 {len(chunks)} 个向量...[/bold cyan]")
    
    ids = [str(uuid.uuid4()) for _ in chunks]
    all_embeddings = await embedding_service.embed_texts([c[1].content for c in chunks])
    metadatas = [
        {
            "doc_type": c[0],
            "chunk_index": c[1].chunk_index if hasattr(c[1], 'chunk_index') else i,
            "section_title": c[1].section_title or "",
        }
        for i, c in enumerate(chunks)
    ]
    documents = [c[1].content for c in chunks]
    
    try:
        inserted_ids = await vector_store.insert(
            collection_name=collection_name,
            ids=ids,
            embeddings=all_embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        
        console.print(f"[bold green]✅ 成功插入 {len(inserted_ids)} 个向量[/bold green]")
        
        count = await vector_store.count(collection_name)
        console.print(f"  当前向量数量: {count}")
        
        return vector_store, collection_name
        
    except Exception as e:
        console.print(f"[bold red]❌ 向量插入失败: {str(e)}[/bold red]")
        import traceback
        traceback.print_exc()
        return None, None


async def test_search(vector_store, collection_name):
    """
    测试知识库检索
    """
    console.print(Panel.fit("🔍 测试知识库检索", style="bold blue"))
    
    from app.knowledge_base.services.embedding import EmbeddingService
    
    embedding_service = EmbeddingService()
    
    test_queries = [
        "报销流程是什么？",
        "系统使用什么技术栈？",
        "如何上传文档？",
    ]
    
    for query in test_queries:
        console.print(f"\n[bold cyan]查询: {query}[/bold cyan]")
        
        try:
            query_embedding = await embedding_service.embed_text(query)
            
            results = await vector_store.search(
                collection_name=collection_name,
                query_embedding=query_embedding,
                top_k=3,
            )
            
            if results:
                for i, result in enumerate(results):
                    score = 1 - result.get("distance", 0)
                    content = result.get("document", "")[:200]
                    console.print(f"\n  [bold]结果 {i+1}[/bold] (相关度: {score:.3f})")
                    console.print(f"  {content}...")
            else:
                console.print("  [yellow]未找到相关结果[/yellow]")
                
        except Exception as e:
            console.print(f"  [red]检索失败: {str(e)}[/red]")
    
    console.print(f"\n[bold green]✅ 知识库检索测试完成[/bold green]")


async def test_rag_agent():
    """
    测试RagAgent完整功能
    """
    console.print(Panel.fit("🤖 测试RagAgent", style="bold blue"))
    
    from app.langchain.agents.rag_agent import RagAgent
    
    agent = RagAgent(user_id="test_user")
    
    console.print("\n[bold cyan]测试 RagAgent 工具封装...[/bold cyan]")
    
    try:
        tool = agent.as_tool()
        console.print(f"  工具名称: {tool.name}")
        console.print(f"  工具描述: {tool.description[:100]}...")
        console.print("[bold green]✅ 工具封装成功[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ 工具封装失败: {str(e)}[/bold red]")
    
    console.print("\n[bold cyan]测试 RagAgent 检索功能...[/bold cyan]")
    
    try:
        results = await agent.search("报销流程", top_k=3)
        
        if results:
            console.print(f"  检索结果数量: {len(results)}")
            for i, r in enumerate(results[:2]):
                console.print(f"\n  [bold]结果 {i+1}[/bold]")
                console.print(f"    相关度: {r.score:.3f}")
                console.print(f"    内容: {r.content[:100]}...")
        else:
            console.print("  [yellow]未找到相关结果（可能知识库为空）[/yellow]")
        
        console.print("[bold green]✅ RagAgent 检索测试完成[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ RagAgent 检索失败: {str(e)}[/bold red]")
        import traceback
        traceback.print_exc()
    
    console.print("\n[bold cyan]测试 RagAgent RAG上下文生成...[/bold cyan]")
    
    try:
        context = await agent.get_rag_context("报销流程", top_k=3)
        
        if context:
            console.print(f"  上下文长度: {len(context)} 字符")
            console.print(f"  上下文预览:\n{context[:500]}...")
        else:
            console.print("  [yellow]未生成上下文（可能知识库为空）[/yellow]")
        
        console.print("[bold green]✅ RAG上下文生成测试完成[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ RAG上下文生成失败: {str(e)}[/bold red]")


async def test_supervisor_integration():
    """
    测试SupervisorAgent集成
    """
    console.print(Panel.fit("🔀 测试SupervisorAgent集成", style="bold blue"))
    
    from app.langchain.agents.supervisor_agent import SupervisorAgent
    from app.langchain.routers.intent_classifier import QueryIntent
    
    agent = SupervisorAgent(
        provider="deepseek",
        user_id="test_user",
    )
    
    test_queries = [
        ("你好，介绍一下你自己", QueryIntent.GENERAL_CHAT),
        ("公司的报销流程是什么？", QueryIntent.KB_QUERY),
        ("帮我写一个Python爬虫", QueryIntent.CODE_TASK),
    ]
    
    console.print("\n[bold cyan]测试意图分类和路由...[/bold cyan]")
    
    for query, expected_intent in test_queries:
        console.print(f"\n[bold]查询:[/bold] {query}")
        
        try:
            result = await agent.intent_classifier.classify(query)
            
            match = "✓" if result.intent == expected_intent else "✗"
            console.print(f"  预期意图: {expected_intent.value}")
            console.print(f"  实际意图: {result.intent.value} {match}")
            console.print(f"  置信度: {result.confidence:.2f}")
            
        except Exception as e:
            console.print(f"  [red]分类失败: {str(e)}[/red]")
    
    console.print(f"\n[bold green]✅ SupervisorAgent集成测试完成[/bold green]")


async def run_pipeline_test():
    """
    运行完整Pipeline测试
    """
    console.print(Panel.fit(
        "[bold]🚀 RagAgent 完整Pipeline测试[/bold]\n\n"
        "测试流程:\n"
        "1. 创建知识库\n"
        "2. 文档解析\n"
        "3. 文档分块\n"
        "4. 向量嵌入\n"
        "5. 向量存储\n"
        "6. 知识库检索\n"
        "7. RagAgent功能\n"
        "8. SupervisorAgent集成",
        style="bold magenta",
    ))
    
    from app.db.session import init_kb_tables
    
    console.print("\n[bold cyan]初始化知识库数据库表...[/bold cyan]")
    try:
        await init_kb_tables()
        console.print("[bold green]✅ 数据库表初始化成功[/bold green]")
    except Exception as e:
        console.print(f"[yellow]数据库表初始化警告: {str(e)}[/yellow]")
    
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        task1 = progress.add_task("创建知识库...", total=None)
        kb_id, db, kb_service = await test_knowledge_base_creation()
        results.append(("知识库创建", kb_id is not None))
        progress.remove_task(task1)
        
        task2 = progress.add_task("解析文档...", total=None)
        parsed_docs, tmpdir = await test_document_parsing()
        results.append(("文档解析", len(parsed_docs) > 0))
        progress.remove_task(task2)
        
        task3 = progress.add_task("文档分块...", total=None)
        chunks = await test_chunking(parsed_docs)
        results.append(("文档分块", len(chunks) > 0))
        progress.remove_task(task3)
        
        task4 = progress.add_task("向量嵌入...", total=None)
        embeddings = await test_embedding(chunks)
        results.append(("向量嵌入", embeddings is not None))
        progress.remove_task(task4)
        
        if kb_id and chunks:
            task5 = progress.add_task("向量存储...", total=None)
            vector_store, collection_name = await test_vector_store(kb_id, chunks, embeddings)
            results.append(("向量存储", vector_store is not None))
            progress.remove_task(task5)
            
            if vector_store:
                task6 = progress.add_task("知识库检索...", total=None)
                await test_search(vector_store, collection_name)
                results.append(("知识库检索", True))
                progress.remove_task(task6)
        else:
            results.append(("向量存储", False))
            results.append(("知识库检索", False))
        
        task7 = progress.add_task("测试RagAgent...", total=None)
        await test_rag_agent()
        results.append(("RagAgent功能", True))
        progress.remove_task(task7)
        
        task8 = progress.add_task("测试SupervisorAgent...", total=None)
        await test_supervisor_integration()
        results.append(("SupervisorAgent集成", True))
        progress.remove_task(task8)
    
    console.print("\n")
    console.print(Panel.fit(
        "[bold]📊 Pipeline测试结果汇总[/bold]",
        style="bold green",
    ))
    
    table = Table(title="")
    table.add_column("测试阶段", style="cyan")
    table.add_column("状态", style="bold")
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        table.add_row(name, status)
    
    console.print(table)
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    console.print(f"\n[bold green]通过: {passed}/{total}[/bold green]")


if __name__ == "__main__":
    asyncio.run(run_pipeline_test())
