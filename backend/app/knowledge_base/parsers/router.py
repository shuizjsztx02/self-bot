from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import asyncio

from .base import DocumentParser, ParsedDocument, ChunkResult
from .markdown_parser import MarkdownParser
from .txt_parser import TXTParser
from .pdf_parser import PDFParser, DoclingParser
from .docx_parser import DocxParser
from .pptx_parser import PPTXParser
from .excel_parser import ExcelParser

logger = logging.getLogger(__name__)


class ParserRouter:
    """
    文档解析路由器
    
    根据文件类型和文档特征选择最优解析器
    支持解析失败回退到Docling处理复杂文档
    """
    
    DOCX_EXTENSIONS = {'.docx', '.doc'}
    PPTX_EXTENSIONS = {'.pptx', '.ppt'}
    EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        self._primary_parsers = {
            '.md': MarkdownParser(),
            '.markdown': MarkdownParser(),
            '.txt': TXTParser(),
            '.pdf': PDFParser(parser_type=self.config.get('pdf_parser', 'auto')),
            '.docx': DocxParser(),
            '.doc': DocxParser(),
            '.pptx': PPTXParser(),
            '.ppt': PPTXParser(),
            '.xlsx': ExcelParser(),
            '.xls': ExcelParser(),
        }
        
        self._fallback_parser = DoclingParser(
            enable_ocr=self.config.get('enable_ocr', True),
            enable_table_structure=self.config.get('enable_table_structure', True),
            use_vlm=self.config.get('use_vlm', False),
        )
        
        self._complex_doc_thresholds = {
            'min_tables': 3,
            'min_images': 5,
            'min_pages': 20,
        }
    
    def get_parser(self, file_path: str) -> Optional[DocumentParser]:
        ext = Path(file_path).suffix.lower()
        return self._primary_parsers.get(ext)
    
    def _is_office_document(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self.DOCX_EXTENSIONS or ext in self.PPTX_EXTENSIONS
    
    def _should_use_docling_fallback(
        self, 
        file_path: str, 
        parsed_doc: Optional[ParsedDocument] = None,
        error: Optional[Exception] = None
    ) -> bool:
        if error is not None:
            logger.warning(f"Primary parser failed for {file_path}: {error}")
            return True
        
        if parsed_doc is None:
            return False
        
        ext = Path(file_path).suffix.lower()
        
        if ext not in self.DOCX_EXTENSIONS and ext not in self.PPTX_EXTENSIONS:
            return False
        
        tables = parsed_doc.tables or []
        table_count = len(tables)
        
        images = parsed_doc.images or []
        image_count = len(images)
        
        pages = parsed_doc.pages or []
        page_count = len(pages)
        
        content_length = len(parsed_doc.content)
        has_low_content = content_length < 100 and page_count > 1
        
        is_complex = (
            table_count >= self._complex_doc_thresholds['min_tables'] or
            image_count >= self._complex_doc_thresholds['min_images'] or
            page_count >= self._complex_doc_thresholds['min_pages'] or
            has_low_content
        )
        
        if is_complex:
            logger.info(
                f"Complex document detected for {file_path}: "
                f"tables={table_count}, images={image_count}, pages={page_count}"
            )
        
        return is_complex
    
    def _check_docling_available(self) -> bool:
        try:
            import docling
            return True
        except ImportError:
            logger.warning("Docling not available for fallback. Install with: pip install docling")
            return False
    
    def get_parser_by_type(self, file_type: str) -> Optional[DocumentParser]:
        type_mapping = {
            'markdown': ['.md', '.markdown'],
            'text': ['.txt'],
            'pdf': ['.pdf'],
            'word': ['.docx', '.doc'],
            'powerpoint': ['.pptx', '.ppt'],
            'excel': ['.xlsx', '.xls'],
        }
        
        for parser_type, extensions in type_mapping.items():
            if file_type.lower() in extensions or f'.{file_type.lower()}' in extensions:
                for ext in extensions:
                    if ext in self._primary_parsers:
                        return self._primary_parsers[ext]
        
        return None
    
    async def parse(
        self, 
        file_path: str,
        enable_fallback: bool = True
    ) -> ParsedDocument:
        parser = self.get_parser(file_path)
        
        if parser is None:
            ext = Path(file_path).suffix.lower()
            raise ValueError(f"Unsupported file type: {ext}")
        
        parsed_doc = None
        primary_error = None
        
        try:
            parsed_doc = await parser.parse(file_path)
        except Exception as e:
            primary_error = e
            logger.warning(f"Primary parser failed for {file_path}: {e}")
        
        if enable_fallback and self._is_office_document(file_path):
            if self._should_use_docling_fallback(file_path, parsed_doc, primary_error):
                if self._check_docling_available():
                    try:
                        logger.info(f"Using Docling fallback for {file_path}")
                        docling_doc = self._fallback_parser.parse(file_path)
                        
                        if parsed_doc is None or self._is_better_parse(docling_doc, parsed_doc):
                            docling_doc.doc_metadata['parser_used'] = 'docling_fallback'
                            docling_doc.doc_metadata['fallback_reason'] = str(primary_error) if primary_error else 'complex_document'
                            return docling_doc
                    except Exception as e:
                        logger.error(f"Docling fallback also failed for {file_path}: {e}")
                        if parsed_doc is None:
                            raise
        
        if parsed_doc is not None:
            parsed_doc.doc_metadata['parser_used'] = 'primary'
            return parsed_doc
        
        if primary_error:
            raise primary_error
        
        raise ValueError(f"Failed to parse {file_path}")
    
    def _is_better_parse(self, new_doc: ParsedDocument, old_doc: ParsedDocument) -> bool:
        new_tables = len(new_doc.tables) if new_doc.tables else 0
        old_tables = len(old_doc.tables) if old_doc.tables else 0
        
        new_images = len(new_doc.images) if new_doc.images else 0
        old_images = len(old_doc.images) if old_doc.images else 0
        
        new_content_len = len(new_doc.content)
        old_content_len = len(old_doc.content)
        
        if new_tables > old_tables:
            return True
        if new_images > old_images:
            return True
        if new_content_len > old_content_len * 1.5:
            return True
        
        return False
    
    async def parse_and_chunk(
        self,
        file_path: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[ChunkResult]:
        parsed_doc = await self.parse(file_path)
        
        return self.chunk_parsed_document(parsed_doc, chunk_size, overlap)
    
    def chunk_parsed_document(
        self,
        parsed_doc: ParsedDocument,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[ChunkResult]:
        file_type = parsed_doc.doc_metadata.get('file_type', '')
        
        if file_type == 'markdown':
            parser = self._primary_parsers.get('.md')
            if hasattr(parser, 'chunk_with_sections'):
                return parser.chunk_with_sections(parsed_doc, chunk_size, overlap)
        
        elif file_type == 'docx':
            parser = self._primary_parsers.get('.docx')
            if hasattr(parser, 'chunk_with_sections'):
                return parser.chunk_with_sections(parsed_doc, chunk_size, overlap)
        
        elif file_type == 'pptx':
            parser = self._primary_parsers.get('.pptx')
            if hasattr(parser, 'chunk_by_slides'):
                return parser.chunk_by_slides(parsed_doc, chunk_size=chunk_size)
        
        elif file_type == 'xlsx':
            parser = self._primary_parsers.get('.xlsx')
            if hasattr(parser, 'chunk_by_sheets'):
                return parser.chunk_by_sheets(parsed_doc, chunk_size)
        
        elif file_type == 'txt':
            parser = self._primary_parsers.get('.txt')
            if hasattr(parser, 'chunk_with_paragraphs'):
                return parser.chunk_with_paragraphs(parsed_doc, chunk_size, overlap)
        
        elif file_type == 'pdf':
            chunks = []
            if parsed_doc.pages:
                for page in parsed_doc.pages:
                    page_content = page['content']
                    if len(page_content) <= chunk_size:
                        chunks.append(ChunkResult(
                            content=page_content,
                            token_count=len(page_content) // 4,
                            page_number=page['page_number'],
                            chunk_metadata={'page_number': page['page_number']},
                        ))
                    else:
                        parser = self._primary_parsers.get('.pdf')
                        text_chunks = parser.chunk_text(page_content, chunk_size, overlap)
                        for i, chunk in enumerate(text_chunks):
                            chunks.append(ChunkResult(
                                content=chunk,
                                token_count=len(chunk) // 4,
                                page_number=page['page_number'],
                                chunk_metadata={
                                    'page_number': page['page_number'],
                                    'chunk_index': i,
                                },
                            ))
            else:
                parser = self._primary_parsers.get('.pdf')
                text_chunks = parser.chunk_text(parsed_doc.content, chunk_size, overlap)
                for i, chunk in enumerate(text_chunks):
                    chunks.append(ChunkResult(
                        content=chunk,
                        token_count=len(chunk) // 4,
                        chunk_metadata={'chunk_index': i},
                    ))
            
            return chunks
        
        parser = list(self._primary_parsers.values())[0]
        text_chunks = parser.chunk_text(parsed_doc.content, chunk_size, overlap)
        
        return [
            ChunkResult(
                content=chunk,
                token_count=len(chunk) // 4,
                chunk_metadata={'chunk_index': i},
            )
            for i, chunk in enumerate(text_chunks)
        ]
    
    def supported_extensions(self) -> List[str]:
        return list(self._primary_parsers.keys())
    
    def is_supported(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        if not ext and file_path.startswith('.'):
            ext = file_path.lower()
        return ext in self._primary_parsers
