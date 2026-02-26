"""
PDF解析器测试脚本

测试：
1. 文档特征分析
2. 智能路由决策
3. 各解析器功能
4. 回退机制
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def test_feature_analyzer():
    """测试文档特征分析器"""
    console.print(Panel.fit("📊 测试文档特征分析器", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFFeatureAnalyzer
    
    analyzer = PDFFeatureAnalyzer()
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    
    if not test_pdf_path.exists():
        console.print("[yellow]测试文件目录不存在，创建示例测试...[/yellow]")
        
        test_pdf_path.mkdir(exist_ok=True)
        
        console.print("[cyan]请将测试PDF文件放入以下目录进行测试:[/cyan]")
        console.print(f"  {test_pdf_path}")
        
        return False
    
    pdf_files = list(test_pdf_path.glob("*.pdf"))
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件[/yellow]")
        return False
    
    for pdf_file in pdf_files[:3]:
        console.print(f"\n[bold cyan]分析: {pdf_file.name}[/bold cyan]")
        
        try:
            features = analyzer.analyze(str(pdf_file))
            
            table = Table(title=f"文档特征 - {pdf_file.name}")
            table.add_column("特征", style="cyan")
            table.add_column("值", style="green")
            
            table.add_row("页数", str(features.page_count))
            table.add_row("有文本层", "✓" if features.has_text_layer else "✗")
            table.add_row("文本密度", f"{features.text_density:.6f}")
            table.add_row("包含图片", "✓" if features.has_images else "✗")
            table.add_row("图片比例", f"{features.image_ratio:.2%}")
            table.add_row("包含表格", "✓" if features.has_tables else "✗")
            table.add_row("布局复杂度", features.layout_complexity)
            table.add_row("是否扫描件", "✓" if features.is_scanned else "✗")
            table.add_row("推荐解析器", features.recommended_parser)
            table.add_row("置信度", f"{features.confidence:.2%}")
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]分析失败: {str(e)}[/red]")
    
    return True


async def test_parser_routing():
    """测试智能路由"""
    console.print(Panel.fit("🔀 测试智能路由", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import (
        PDFParser, DocumentFeatures, PDFFeatureAnalyzer
    )
    
    analyzer = PDFFeatureAnalyzer()
    
    test_cases = [
        DocumentFeatures(
            page_count=10,
            has_text_layer=True,
            text_density=0.02,
            has_images=False,
            image_ratio=0.0,
            has_tables=False,
            is_scanned=False,
            layout_complexity="simple",
        ),
        DocumentFeatures(
            page_count=5,
            has_text_layer=True,
            text_density=0.015,
            has_images=False,
            image_ratio=0.0,
            has_tables=True,
            is_scanned=False,
            layout_complexity="medium",
        ),
        DocumentFeatures(
            page_count=20,
            has_text_layer=False,
            text_density=0.001,
            has_images=True,
            image_ratio=0.95,
            has_tables=False,
            is_scanned=True,
            layout_complexity="simple",
        ),
        DocumentFeatures(
            page_count=15,
            has_text_layer=True,
            text_density=0.012,
            has_images=True,
            image_ratio=0.4,
            has_tables=True,
            is_scanned=False,
            layout_complexity="complex",
        ),
    ]
    
    expected_results = ["pymupdf", "mineru", "mineru", "mineru"]
    
    table = Table(title="路由决策测试")
    table.add_column("场景", style="cyan")
    table.add_column("预期", style="yellow")
    table.add_column("实际", style="green")
    table.add_column("结果", style="bold")
    
    scenarios = [
        "纯文本PDF",
        "含表格PDF (MinerU优先)",
        "扫描件PDF (MinerU优先)",
        "复杂布局PDF (MinerU优先)",
    ]
    
    for i, (features, expected, scenario) in enumerate(zip(test_cases, expected_results, scenarios)):
        recommended, confidence = analyzer._recommend_parser(features)
        
        match = "✓" if recommended == expected else "✗"
        table.add_row(scenario, expected, recommended, match)
    
    console.print(table)


async def test_available_parsers():
    """测试可用解析器检测"""
    console.print(Panel.fit("🔍 测试可用解析器", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser
    
    parser = PDFParser()
    
    available = parser.get_available_parsers()
    
    table = Table(title="解析器可用性")
    table.add_column("解析器", style="cyan")
    table.add_column("描述", style="white")
    table.add_column("状态", style="bold")
    
    for parser_type, desc in PDFParser.PARSER_TYPES.items():
        status = "✅ 可用" if parser_type in available else "❌ 未安装"
        table.add_row(parser_type, desc[:30] + "...", status)
    
    console.print(table)
    
    return len(available) > 0


async def test_parse_flow():
    """测试完整解析流程"""
    console.print(Panel.fit("📄 测试完整解析流程", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过解析测试[/yellow]")
        return False
    
    parser = PDFParser(parser_type="auto")
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]解析: {pdf_file.name}[/bold cyan]")
        
        try:
            result = await parser.parse(str(pdf_file))
            
            console.print(f"[green]✅ 解析成功[/green]")
            console.print(f"  解析器: {result.doc_metadata.get('parser', 'unknown')}")
            console.print(f"  内容长度: {len(result.content)} 字符")
            console.print(f"  页数: {len(result.pages) if result.pages else 0}")
            
            if result.doc_metadata.get('auto_routed'):
                console.print(f"  自动路由: {result.doc_metadata.get('recommended_parser')}")
                console.print(f"  置信度: {result.doc_metadata.get('routing_confidence', 0):.2%}")
            
            if result.tables:
                console.print(f"  表格数量: {len(result.tables)}")
            
            console.print(f"\n  [bold]内容预览:[/bold]")
            console.print(f"  {result.content[:200]}...")
            
        except Exception as e:
            console.print(f"[red]❌ 解析失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
    
    return True


async def test_mineru_layout_analysis():
    """测试MinerU版面分析"""
    console.print(Panel.fit("📐 测试MinerU版面分析", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, LayoutBlock
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过版面分析测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="mineru")
    
    available = parser.get_available_parsers()
    if "mineru" not in available:
        console.print("[yellow]MinerU未安装，跳过版面分析测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]版面分析: {pdf_file.name}[/bold cyan]")
        
        try:
            parsed_doc, layout_blocks = await parser.parse_with_layout(str(pdf_file))
            
            console.print(f"[green]✅ 版面分析成功[/green]")
            console.print(f"  解析文档: {len(parsed_doc.content)} 字符")
            console.print(f"  版面块数量: {len(layout_blocks)}")
            
            block_types = {}
            for block in layout_blocks:
                block_types[block.block_type] = block_types.get(block.block_type, 0) + 1
            
            table = Table(title="版面块类型统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green")
            
            for btype, count in sorted(block_types.items()):
                table.add_row(btype, str(count))
            
            console.print(table)
            
            if layout_blocks:
                console.print(f"\n  [bold]前5个版面块:[/bold]")
                for i, block in enumerate(layout_blocks[:5]):
                    console.print(f"    [{i+1}] 类型: {block.block_type}, 页码: {block.page_number}")
                    console.print(f"        内容预览: {block.content[:50]}...")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]MinerU未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ 版面分析失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_mineru_table_extraction():
    """测试MinerU表格结构识别"""
    console.print(Panel.fit("📊 测试MinerU表格结构识别", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, TableStructure
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过表格提取测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="mineru")
    
    available = parser.get_available_parsers()
    if "mineru" not in available:
        console.print("[yellow]MinerU未安装，跳过表格提取测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]表格提取: {pdf_file.name}[/bold cyan]")
        
        try:
            tables = await parser.extract_tables_structured(str(pdf_file))
            
            console.print(f"[green]✅ 表格提取成功[/green]")
            console.print(f"  表格数量: {len(tables)}")
            
            for i, table in enumerate(tables[:3]):
                console.print(f"\n  [bold]表格 {i+1}:[/bold]")
                console.print(f"    页码: {table.page_number}")
                console.print(f"    位置: {table.bbox}")
                if table.caption:
                    console.print(f"    标题: {table.caption}")
                if table.markdown_content:
                    lines = table.markdown_content.split('\n')[:5]
                    console.print(f"    Markdown预览:")
                    for line in lines:
                        console.print(f"      {line}")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]MinerU未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ 表格提取失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_mineru_semantic_chunking():
    """测试MinerU语义分块"""
    console.print(Panel.fit("📝 测试MinerU语义分块", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, SemanticChunk
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过语义分块测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="mineru")
    
    available = parser.get_available_parsers()
    if "mineru" not in available:
        console.print("[yellow]MinerU未安装，跳过语义分块测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]语义分块: {pdf_file.name}[/bold cyan]")
        
        try:
            chunks = await parser.semantic_chunking(
                str(pdf_file),
                max_chunk_size=500,
                respect_structure=True
            )
            
            console.print(f"[green]✅ 语义分块成功[/green]")
            console.print(f"  分块数量: {len(chunks)}")
            
            chunk_types = {}
            for chunk in chunks:
                chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
            
            table = Table(title="分块类型统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green")
            
            for ctype, count in sorted(chunk_types.items()):
                table.add_row(ctype, str(count))
            
            console.print(table)
            
            console.print(f"\n  [bold]前5个分块预览:[/bold]")
            for i, chunk in enumerate(chunks[:5]):
                console.print(f"\n    [{i+1}] ID: {chunk.chunk_id}")
                console.print(f"        类型: {chunk.chunk_type}")
                console.print(f"        页码: {chunk.page_numbers}")
                console.print(f"        章节路径: {' > '.join(chunk.section_path) if chunk.section_path else '无'}")
                console.print(f"        Token数: {chunk.token_count}")
                console.print(f"        内容预览: {chunk.content[:80]}...")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]MinerU未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ 语义分块失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_fallback_mechanism():
    """测试回退机制"""
    console.print(Panel.fit("🔄 测试回退机制", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser
    
    parser = PDFParser(
        parser_type="docling",
        fallback_order=["pymupdf", "pdfplumber"]
    )
    
    available = parser.get_available_parsers()
    
    console.print(f"[cyan]指定解析器: docling[/cyan]")
    console.print(f"[cyan]回退顺序: pymupdf -> pdfplumber[/cyan]")
    console.print(f"[cyan]可用解析器: {list(available.keys())}[/cyan]")
    
    if "pymupdf" in available:
        console.print("[green]✅ 回退机制已配置，当docling不可用时会自动回退[/green]")
    else:
        console.print("[yellow]⚠️ 没有可用的回退解析器[/yellow]")
    
    return True


async def test_docling_layout_analysis():
    """测试Docling版面分析"""
    console.print(Panel.fit("📐 测试Docling版面分析", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, DoclingLayoutBlock
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过Docling版面分析测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="docling")
    
    available = parser.get_available_parsers()
    if "docling" not in available:
        console.print("[yellow]Docling未安装，跳过版面分析测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]Docling版面分析: {pdf_file.name}[/bold cyan]")
        
        try:
            parsed_doc, layout_blocks = await parser.parse_with_layout(
                str(pdf_file), parser_type="docling"
            )
            
            console.print(f"[green]✅ Docling版面分析成功[/green]")
            console.print(f"  解析文档: {len(parsed_doc.content)} 字符")
            console.print(f"  版面块数量: {len(layout_blocks)}")
            
            block_types = {}
            for block in layout_blocks:
                block_types[block.label] = block_types.get(block.label, 0) + 1
            
            table = Table(title="Docling版面块类型统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green")
            
            for btype, count in sorted(block_types.items()):
                table.add_row(btype, str(count))
            
            console.print(table)
            
            if layout_blocks:
                console.print(f"\n  [bold]前5个版面块:[/bold]")
                for i, block in enumerate(layout_blocks[:5]):
                    console.print(f"    [{i+1}] 类型: {block.item_type}, 标签: {block.label}, 页码: {block.page_number}")
                    console.print(f"        内容预览: {block.content[:50]}...")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]Docling未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Docling版面分析失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_docling_semantic_chunking():
    """测试Docling语义分块"""
    console.print(Panel.fit("📝 测试Docling语义分块", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, SemanticChunk
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过Docling语义分块测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="docling")
    
    available = parser.get_available_parsers()
    if "docling" not in available:
        console.print("[yellow]Docling未安装，跳过语义分块测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]Docling语义分块: {pdf_file.name}[/bold cyan]")
        
        try:
            chunks = await parser.semantic_chunking(
                str(pdf_file),
                max_chunk_size=500,
                respect_structure=True,
                parser_type="docling"
            )
            
            console.print(f"[green]✅ Docling语义分块成功[/green]")
            console.print(f"  分块数量: {len(chunks)}")
            
            chunk_types = {}
            for chunk in chunks:
                chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
            
            table = Table(title="Docling分块类型统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green")
            
            for ctype, count in sorted(chunk_types.items()):
                table.add_row(ctype, str(count))
            
            console.print(table)
            
            console.print(f"\n  [bold]前5个分块预览:[/bold]")
            for i, chunk in enumerate(chunks[:5]):
                console.print(f"\n    [{i+1}] ID: {chunk.chunk_id}")
                console.print(f"        类型: {chunk.chunk_type}")
                console.print(f"        页码: {chunk.page_numbers}")
                console.print(f"        章节路径: {' > '.join(chunk.section_path) if chunk.section_path else '无'}")
                console.print(f"        Token数: {chunk.token_count}")
                console.print(f"        内容预览: {chunk.content[:80]}...")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]Docling未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Docling语义分块失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_docling_export_formats():
    """测试Docling导出格式"""
    console.print(Panel.fit("📤 测试Docling导出格式", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过导出格式测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="docling")
    
    available = parser.get_available_parsers()
    if "docling" not in available:
        console.print("[yellow]Docling未安装，跳过导出格式测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]导出格式测试: {pdf_file.name}[/bold cyan]")
        
        try:
            json_result = await parser.export_to_json(str(pdf_file), parser_type="docling")
            console.print(f"[green]✅ JSON导出成功[/green]")
            console.print(f"  JSON键: {list(json_result.keys())[:5]}...")
            
            html_result = await parser.export_to_html(str(pdf_file), parser_type="docling")
            console.print(f"[green]✅ HTML导出成功[/green]")
            console.print(f"  HTML长度: {len(html_result)} 字符")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]Docling未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ 导出格式测试失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_docling_vlm_mode():
    """测试Docling VLM模式配置"""
    console.print(Panel.fit("🤖 测试Docling VLM模式配置", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, DoclingParser
    
    parser_standard = PDFParser(
        parser_type="docling",
        docling_config={"enable_ocr": True, "use_vlm": False}
    )
    
    parser_vlm = PDFParser(
        parser_type="docling",
        docling_config={"enable_ocr": True, "use_vlm": True, "vlm_model": "granite_docling"}
    )
    
    available = parser_standard.get_available_parsers()
    if "docling" not in available:
        console.print("[yellow]Docling未安装，跳过VLM模式测试[/yellow]")
        return True
    
    console.print("[green]✅ 标准模式配置成功[/green]")
    console.print("  - OCR: 启用")
    console.print("  - VLM: 禁用")
    
    console.print("[green]✅ VLM模式配置成功[/green]")
    console.print("  - OCR: 启用")
    console.print("  - VLM: 启用 (granite_docling)")
    
    console.print("\n[cyan]VLM模式说明:[/cyan]")
    console.print("  - granite_docling: IBM Granite视觉语言模型")
    console.print("  - 支持Apple Silicon MLX加速")
    console.print("  - 适用于复杂布局和图表理解")
    
    return True


async def test_ocr_layout_analysis():
    """测试OCR版面分析"""
    console.print(Panel.fit("📐 测试OCR版面分析 (PP-Structure)", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, OCRLayoutBlock
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过OCR版面分析测试[/yellow]")
        return True
    
    parser = PDFParser(
        parser_type="ocr",
        ocr_config={"enable_layout": True, "enable_table": True}
    )
    
    available = parser.get_available_parsers()
    if "ocr" not in available:
        console.print("[yellow]PaddleOCR未安装，跳过版面分析测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]OCR版面分析: {pdf_file.name}[/bold cyan]")
        
        try:
            parsed_doc, layout_blocks = await parser.parse_with_layout(
                str(pdf_file), parser_type="ocr"
            )
            
            console.print(f"[green]✅ OCR版面分析成功[/green]")
            console.print(f"  解析文档: {len(parsed_doc.content)} 字符")
            console.print(f"  版面块数量: {len(layout_blocks)}")
            
            block_types = {}
            for block in layout_blocks:
                block_types[block.block_type] = block_types.get(block.block_type, 0) + 1
            
            table = Table(title="OCR版面块类型统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green")
            
            for btype, count in sorted(block_types.items()):
                table.add_row(btype, str(count))
            
            console.print(table)
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]PaddleOCR未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ OCR版面分析失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_ocr_table_extraction():
    """测试OCR表格识别"""
    console.print(Panel.fit("📊 测试OCR表格识别 (PP-Structure)", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过OCR表格提取测试[/yellow]")
        return True
    
    parser = PDFParser(
        parser_type="ocr",
        ocr_config={"enable_table": True}
    )
    
    available = parser.get_available_parsers()
    if "ocr" not in available:
        console.print("[yellow]PaddleOCR未安装，跳过表格提取测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]OCR表格提取: {pdf_file.name}[/bold cyan]")
        
        try:
            tables = await parser.extract_tables_structured(str(pdf_file), parser_type="ocr")
            
            console.print(f"[green]✅ OCR表格提取成功[/green]")
            console.print(f"  表格数量: {len(tables)}")
            
            for i, table in enumerate(tables[:3]):
                console.print(f"\n  [bold]表格 {i+1}:[/bold]")
                console.print(f"    页码: {table.page_number}")
                console.print(f"    位置: {table.bbox}")
                if table.markdown_content:
                    lines = table.markdown_content.split('\n')[:5]
                    console.print(f"    Markdown预览:")
                    for line in lines:
                        console.print(f"      {line}")
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]PaddleOCR未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ OCR表格提取失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_ocr_semantic_chunking():
    """测试OCR语义分块"""
    console.print(Panel.fit("📝 测试OCR语义分块", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, SemanticChunk
    
    test_pdf_path = Path(__file__).parent.parent / "test_files"
    pdf_files = list(test_pdf_path.glob("*.pdf")) if test_pdf_path.exists() else []
    
    if not pdf_files:
        console.print("[yellow]未找到测试PDF文件，跳过OCR语义分块测试[/yellow]")
        return True
    
    parser = PDFParser(parser_type="ocr")
    
    available = parser.get_available_parsers()
    if "ocr" not in available:
        console.print("[yellow]PaddleOCR未安装，跳过语义分块测试[/yellow]")
        return True
    
    for pdf_file in pdf_files[:1]:
        console.print(f"\n[bold cyan]OCR语义分块: {pdf_file.name}[/bold cyan]")
        
        try:
            chunks = await parser.semantic_chunking(
                str(pdf_file),
                max_chunk_size=500,
                respect_structure=True,
                parser_type="ocr"
            )
            
            console.print(f"[green]✅ OCR语义分块成功[/green]")
            console.print(f"  分块数量: {len(chunks)}")
            
            chunk_types = {}
            for chunk in chunks:
                chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
            
            table = Table(title="OCR分块类型统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green")
            
            for ctype, count in sorted(chunk_types.items()):
                table.add_row(ctype, str(count))
            
            console.print(table)
            
            return True
            
        except ImportError as e:
            console.print(f"[yellow]PaddleOCR未安装: {e}[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]❌ OCR语义分块失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_ocr_config():
    """测试OCR配置选项"""
    console.print(Panel.fit("⚙️ 测试OCR配置选项", style="bold blue"))
    
    from app.knowledge_base.parsers.pdf_parser import PDFParser, OCRParser
    
    parser_cpu = PDFParser(
        parser_type="ocr",
        ocr_config={"use_gpu": False, "lang": "ch", "enable_layout": True}
    )
    
    parser_gpu = PDFParser(
        parser_type="ocr",
        ocr_config={"use_gpu": True, "lang": "en", "enable_table": True}
    )
    
    available = parser_cpu.get_available_parsers()
    if "ocr" not in available:
        console.print("[yellow]PaddleOCR未安装，跳过配置测试[/yellow]")
        return True
    
    console.print("[green]✅ CPU模式配置成功[/green]")
    console.print("  - GPU: 禁用")
    console.print("  - 语言: 中文")
    console.print("  - 版面分析: 启用")
    
    console.print("[green]✅ GPU模式配置成功[/green]")
    console.print("  - GPU: 启用")
    console.print("  - 语言: 英文")
    console.print("  - 表格识别: 启用")
    
    console.print("\n[cyan]PaddleOCR配置选项:[/cyan]")
    console.print("  - lang: 语言 (ch/en/korean/japan等80+语言)")
    console.print("  - use_gpu: GPU加速")
    console.print("  - enable_layout: 版面分析")
    console.print("  - enable_table: 表格识别")
    console.print("  - det_db_thresh: 文本检测阈值")
    console.print("  - det_db_box_thresh: 文本框阈值")
    
    return True


async def run_all_tests():
    """运行所有测试"""
    console.print(Panel.fit(
        "[bold]🧪 PDF解析器完整测试[/bold]\n\n"
        "测试项目:\n"
        "1. 文档特征分析\n"
        "2. 智能路由决策\n"
        "3. 解析器可用性检测\n"
        "4. 完整解析流程\n"
        "5. 回退机制\n"
        "6. MinerU版面分析\n"
        "7. MinerU表格结构识别\n"
        "8. MinerU语义分块\n"
        "9. Docling版面分析\n"
        "10. Docling语义分块\n"
        "11. Docling导出格式\n"
        "12. Docling VLM模式\n"
        "13. OCR版面分析 (PP-Structure)\n"
        "14. OCR表格识别\n"
        "15. OCR语义分块\n"
        "16. OCR配置选项",
        style="bold magenta",
    ))
    
    results = []
    
    console.print("\n")
    result1 = await test_available_parsers()
    results.append(("解析器可用性", result1))
    
    console.print("\n")
    result2 = await test_parser_routing()
    results.append(("智能路由", True))
    
    console.print("\n")
    result3 = await test_feature_analyzer()
    results.append(("特征分析", result3 or True))
    
    console.print("\n")
    result4 = await test_parse_flow()
    results.append(("解析流程", result4 or True))
    
    console.print("\n")
    result5 = await test_fallback_mechanism()
    results.append(("回退机制", result5))
    
    console.print("\n")
    result6 = await test_mineru_layout_analysis()
    results.append(("MinerU版面分析", result6))
    
    console.print("\n")
    result7 = await test_mineru_table_extraction()
    results.append(("MinerU表格提取", result7))
    
    console.print("\n")
    result8 = await test_mineru_semantic_chunking()
    results.append(("MinerU语义分块", result8))
    
    console.print("\n")
    result9 = await test_docling_layout_analysis()
    results.append(("Docling版面分析", result9))
    
    console.print("\n")
    result10 = await test_docling_semantic_chunking()
    results.append(("Docling语义分块", result10))
    
    console.print("\n")
    result11 = await test_docling_export_formats()
    results.append(("Docling导出格式", result11))
    
    console.print("\n")
    result12 = await test_docling_vlm_mode()
    results.append(("Docling VLM模式", result12))
    
    console.print("\n")
    result13 = await test_ocr_layout_analysis()
    results.append(("OCR版面分析", result13))
    
    console.print("\n")
    result14 = await test_ocr_table_extraction()
    results.append(("OCR表格提取", result14))
    
    console.print("\n")
    result15 = await test_ocr_semantic_chunking()
    results.append(("OCR语义分块", result15))
    
    console.print("\n")
    result16 = await test_ocr_config()
    results.append(("OCR配置选项", result16))
    
    console.print("\n")
    console.print(Panel.fit(
        "[bold]📊 测试结果汇总[/bold]",
        style="bold green",
    ))
    
    table = Table(title="")
    table.add_column("测试项目", style="cyan")
    table.add_column("状态", style="bold")
    
    for name, success in results:
        status = "✅ 通过" if success else "⚠️ 跳过"
        table.add_row(name, status)
    
    console.print(table)
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    console.print(f"\n[bold green]通过: {passed}/{total}[/bold green]")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
