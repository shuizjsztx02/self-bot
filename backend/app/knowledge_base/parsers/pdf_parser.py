"""
PDF解析器模块

支持多种PDF解析策略：
- pymupdf: 快速文本提取，适用于文本型PDF
- pdfplumber: 表格提取，适用于包含表格的PDF
- ocr (PaddleOCR): OCR识别，适用于扫描件/图片型PDF
- docling: 复杂布局文档解析
- mineru: MinerU深度文档解析（集成DeepDoc能力）

智能路由策略：
根据文档特征自动选择最佳解析器
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import asyncio
import logging
import json
import tempfile
import os

from .base import DocumentParser, ParsedDocument, ChunkResult

logger = logging.getLogger(__name__)


@dataclass
class DocumentFeatures:
    """
    文档特征分析结果（增强版）
    
    用于智能路由决策的特征集合
    """
    page_count: int = 0
    file_size: int = 0
    
    has_text_layer: bool = False
    text_density: float = 0.0
    
    has_images: bool = False
    image_ratio: float = 0.0
    is_scanned: bool = False
    
    has_tables: bool = False
    table_count: int = 0
    table_ratio: float = 0.0
    
    has_formulas: bool = False
    formula_ratio: float = 0.0
    
    has_multi_column: bool = False
    column_count: int = 1
    
    has_charts: bool = False
    has_code_blocks: bool = False
    
    language: str = "unknown"
    layout_complexity: str = "simple"
    
    recommended_parser: str = "pymupdf"
    confidence: float = 0.0
    fallback_order: List[str] = field(default_factory=list)
    
    sample_pages_used: int = 0
    analysis_time_ms: int = 0


@dataclass
class LayoutBlock:
    """版面分析块"""
    block_type: str
    content: str
    bbox: Tuple[float, float, float, float]
    page_number: int
    confidence: float = 1.0
    children: List['LayoutBlock'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableStructure:
    """表格结构"""
    page_number: int
    bbox: Tuple[float, float, float, float]
    html_content: str
    markdown_content: str
    caption: Optional[str] = None
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)


@dataclass
class SemanticChunk:
    """语义分块"""
    chunk_id: str
    content: str
    chunk_type: str
    page_numbers: List[int]
    parent_title: Optional[str] = None
    section_path: List[str] = field(default_factory=list)
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PDFFeatureAnalyzer:
    """
    PDF文档特征分析器（增强版）
    
    智能采样策略：
    - 小文件(<=10页)：全量分析
    - 中等文件(11-50页)：采样20%页数，最少10页
    - 大文件(>50页)：采样10%页数，最少10页
    
    检测能力：
    - 文本层、图像、表格
    - 公式、多栏布局
    - 图表、代码块
    - 语言识别
    """
    
    FORMULA_PATTERNS = [
        '∑', '∫', '∂', '√', 'π', 'α', 'β', 'γ', 'δ', 'ε', 'θ', 'λ', 'μ', 'σ', 'φ', 'ω',
        '→', '←', '↔', '⇒', '⇔', '∈', '∉', '⊂', '⊃', '∪', '∩', '∞', '≈', '≠', '≤', '≥',
        '×', '÷', '±', '∓', '·', '∘', '⊕', '⊗',
        '²', '³', '⁰', '¹', '⁴', '⁵', '⁶', '⁷', '⁸', '⁹',
        '₀', '₁', '₂', '₃', '₄', '₅', '₆', '₇', '₈', '₉',
    ]
    
    LATEX_PATTERNS = [
        '\\frac', '\\sqrt', '\\sum', '\\int', '\\prod', '\\lim', '\\log', '\\sin', '\\cos',
        '\\begin{equation', '\\begin{align', '\\begin{matrix', '\\begin{array',
        '\\left(', '\\right)', '\\left[', '\\right]', '\\left\\{', '\\right\\}',
    ]
    
    CODE_INDICATORS = [
        'def ', 'class ', 'function ', 'import ', 'from ', 'return ', 'if __name__',
        'public ', 'private ', 'void ', 'static ', 'const ', 'let ', 'var ',
        '#include', '#import', 'package ', 'func ', 'fn ',
    ]
    
    def analyze(self, file_path: str, sample_pages: int = None) -> DocumentFeatures:
        import time
        start_time = time.time()
        
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")
        
        doc = fitz.open(file_path)
        page_count = len(doc)
        file_size = os.path.getsize(file_path)
        
        if sample_pages is None:
            sample_pages = self._calculate_sample_pages(page_count)
        
        features = DocumentFeatures(
            page_count=page_count,
            file_size=file_size,
            sample_pages_used=min(sample_pages, page_count)
        )
        
        if page_count == 0:
            doc.close()
            return features
        
        sample_indices = self._get_sample_indices(page_count, sample_pages)
        
        total_text = []
        total_images = 0
        total_area = 0
        text_pages = 0
        image_pages = 0
        formula_pages = 0
        multi_column_pages = 0
        code_pages = 0
        
        for page_num in sample_indices:
            page = doc[page_num]
            page_area = page.rect.width * page.rect.height
            text = page.get_text()
            images = page.get_images()
            
            total_text.append(text)
            total_images += len(images)
            total_area += page_area
            
            if len(text.strip()) > 50:
                text_pages += 1
            
            if images:
                image_pages += 1
            
            if self._detect_formulas_in_page(page, text):
                formula_pages += 1
            
            if self._detect_multi_column_in_page(page):
                multi_column_pages += 1
            
            if self._detect_code_in_page(text):
                code_pages += 1
        
        doc.close()
        
        sample_count = len(sample_indices)
        
        features.has_text_layer = text_pages > sample_count * 0.5
        features.has_images = total_images > 0
        features.image_ratio = image_pages / sample_count if sample_count > 0 else 0
        
        if total_area > 0:
            features.text_density = len('\n'.join(total_text)) / total_area
        
        features.is_scanned = self._detect_scanned_pdf(
            features.has_text_layer,
            features.text_density,
            features.image_ratio
        )
        
        features.has_tables, features.table_count, features.table_ratio = self._detect_tables_enhanced(
            file_path, page_count, sample_indices
        )
        
        features.has_formulas = formula_pages > 0
        features.formula_ratio = formula_pages / sample_count if sample_count > 0 else 0
        
        features.has_multi_column = multi_column_pages > sample_count * 0.3
        features.column_count = 2 if features.has_multi_column else 1
        
        features.has_code_blocks = code_pages > 0
        
        all_text = '\n'.join(total_text)
        features.language = self._detect_language(all_text)
        
        features.has_charts = self._detect_charts(all_text)
        
        features.layout_complexity = self._assess_layout_complexity_v2(features)
        
        features.recommended_parser, features.confidence = self._recommend_parser_v2(features)
        
        features.fallback_order = self._get_dynamic_fallback_order(features)
        
        features.analysis_time_ms = int((time.time() - start_time) * 1000)
        
        return features
    
    def _calculate_sample_pages(self, page_count: int) -> int:
        if page_count <= 10:
            return page_count
        elif page_count <= 50:
            return max(10, page_count // 5)
        else:
            return max(10, page_count // 10)
    
    def _get_sample_indices(self, page_count: int, sample_pages: int) -> List[int]:
        if sample_pages >= page_count:
            return list(range(page_count))
        
        step = page_count / sample_pages
        indices = [int(i * step) for i in range(sample_pages)]
        return sorted(set(indices))
    
    def _detect_formulas_in_page(self, page, text: str) -> bool:
        for pattern in self.FORMULA_PATTERNS:
            if pattern in text:
                return True
        
        for pattern in self.LATEX_PATTERNS:
            if pattern.lower() in text.lower():
                return True
        
        return False
    
    def _detect_multi_column_in_page(self, page) -> bool:
        try:
            blocks = page.get_text("dict").get("blocks", [])
            
            text_blocks = [b for b in blocks if b.get('type') == 0]
            if len(text_blocks) < 4:
                return False
            
            x_positions = []
            for block in text_blocks:
                bbox = block.get('bbox', (0, 0, 0, 0))
                x_center = (bbox[0] + bbox[2]) / 2
                x_positions.append(x_center)
            
            if not x_positions:
                return False
            
            page_width = page.rect.width
            left_count = sum(1 for x in x_positions if x < page_width / 3)
            middle_count = sum(1 for x in x_positions if page_width / 3 <= x < page_width * 2 / 3)
            right_count = sum(1 for x in x_positions if x >= page_width * 2 / 3)
            
            has_left = left_count >= 2
            has_right = right_count >= 2
            
            return has_left and has_right
        except Exception:
            return False
    
    def _detect_code_in_page(self, text: str) -> bool:
        code_indicator_count = 0
        for indicator in self.CODE_INDICATORS:
            if indicator in text:
                code_indicator_count += 1
        
        if code_indicator_count >= 2:
            return True
        
        lines = text.split('\n')
        indent_lines = sum(1 for line in lines if line.startswith('    ') or line.startswith('\t'))
        
        if len(lines) > 5 and indent_lines / len(lines) > 0.3:
            return True
        
        return False
    
    def _detect_language(self, text: str) -> str:
        if not text:
            return "unknown"
        
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total_alpha = chinese_chars + english_chars
        
        if total_alpha == 0:
            return "unknown"
        
        chinese_ratio = chinese_chars / total_alpha
        
        if chinese_ratio > 0.5:
            return "zh"
        elif chinese_ratio > 0.1:
            return "zh-en"
        else:
            return "en"
    
    def _detect_charts(self, text: str) -> bool:
        chart_keywords = [
            'figure', 'fig.', 'chart', 'graph', 'diagram',
            '图', '图表', '示意图', '流程图',
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in chart_keywords)
    
    def _detect_scanned_pdf(
        self,
        has_text_layer: bool,
        text_density: float,
        image_ratio: float
    ) -> bool:
        if not has_text_layer and image_ratio > 0.8:
            return True
        if text_density < 0.005 and image_ratio > 0.5:
            return True
        return False
    
    def _detect_tables_enhanced(
        self, 
        file_path: str, 
        page_count: int,
        sample_indices: List[int]
    ) -> Tuple[bool, int, float]:
        table_count = 0
        pages_with_tables = 0
        
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num in sample_indices:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        tables = page.find_tables()
                        if tables:
                            table_count += len(tables)
                            pages_with_tables += 1
        except Exception:
            pass
        
        sample_count = len(sample_indices) if sample_indices else 1
        table_ratio = pages_with_tables / sample_count
        
        return table_count > 0, table_count, table_ratio
    
    def _assess_layout_complexity_v2(self, features: DocumentFeatures) -> str:
        score = 0
        
        if features.has_tables:
            score += 2
            if features.table_count > 5:
                score += 1
        
        if features.has_images:
            score += 1
            if features.image_ratio > 0.5:
                score += 1
        
        if features.has_formulas:
            score += 2
            if features.formula_ratio > 0.3:
                score += 1
        
        if features.has_multi_column:
            score += 2
        
        if features.has_charts:
            score += 1
        
        if features.has_code_blocks:
            score += 1
        
        if score <= 1:
            return "simple"
        elif score <= 4:
            return "medium"
        else:
            return "complex"
    
    def _recommend_parser_v2(self, features: DocumentFeatures) -> Tuple[str, float]:
        if features.is_scanned:
            if features.page_count > 50:
                return ("mineru", 0.95)
            elif features.layout_complexity == "complex":
                return ("docling", 0.90)
            else:
                return ("ocr", 0.90)
        
        if features.has_formulas:
            return ("mineru", 0.92)
        
        if features.has_multi_column:
            return ("docling", 0.88)
        
        if features.has_text_layer and not features.has_images and not features.has_tables:
            return ("pymupdf", 0.98)
        
        if features.has_tables:
            if features.table_ratio > 0.3 and features.layout_complexity == "simple":
                return ("pdfplumber", 0.92)
            elif features.layout_complexity in ["medium", "complex"]:
                return ("mineru", 0.90)
            elif features.has_images:
                return ("mineru", 0.88)
            else:
                return ("pdfplumber", 0.85)
        
        if features.has_images and features.has_text_layer:
            if features.image_ratio > 0.5:
                return ("ocr", 0.85)
            elif features.layout_complexity == "complex":
                return ("docling", 0.85)
            else:
                return ("pymupdf", 0.80)
        
        if features.has_text_layer:
            return ("pymupdf", 0.90)
        
        return ("pymupdf", 0.70)
    
    def _get_dynamic_fallback_order(self, features: DocumentFeatures) -> List[str]:
        if features.is_scanned:
            return ["ocr", "mineru", "docling", "pymupdf"]
        
        if features.has_tables:
            return ["pdfplumber", "mineru", "docling", "pymupdf"]
        
        if features.layout_complexity == "complex":
            return ["docling", "mineru", "ocr", "pymupdf"]
        
        if features.has_formulas:
            return ["mineru", "docling", "ocr", "pymupdf"]
        
        return ["pymupdf", "pdfplumber", "docling", "mineru", "ocr"]


class PyMuPDFParser:
    """PyMuPDF解析器 - 快速文本提取"""
    
    def parse(self, file_path: str) -> ParsedDocument:
        import fitz
        
        doc = fitz.open(file_path)
        
        all_text = []
        pages = []
        sections = []
        doc_metadata = {
            'filename': Path(file_path).name,
            'file_type': 'pdf',
            'page_count': len(doc),
            'parser': 'pymupdf',
        }
        
        if doc.metadata:
            if doc.metadata.get('title'):
                doc_metadata['title'] = doc.metadata['title']
            if doc.metadata.get('author'):
                doc_metadata['author'] = doc.metadata['author']
            if doc.metadata.get('subject'):
                doc_metadata['subject'] = doc.metadata['subject']
        
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            all_text.append(text)
            
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get('type') == 0:
                    font_size = 0
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            if span.get('size', 0) > font_size:
                                font_size = span['size']
                    
                    block_text = ""
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            block_text += span.get('text', '')
                        block_text += '\n'
                    
                    if font_size > 14:
                        sections.append({
                            'title': block_text.strip(),
                            'level': 1 if font_size > 18 else 2,
                            'page_number': page_num + 1,
                        })
            
            pages.append({
                'page_number': page_num + 1,
                'content': text,
                'char_count': len(text),
            })
        
        doc.close()
        
        content = '\n\n'.join(all_text)
        
        return ParsedDocument(
            content=content,
            doc_metadata=doc_metadata,
            pages=pages,
            sections=sections if sections else None,
        )


class PDFPlumberParser:
    """PDFPlumber解析器 - 表格提取"""
    
    def parse(self, file_path: str) -> ParsedDocument:
        import pdfplumber
        
        all_text = []
        pages = []
        tables = []
        doc_metadata = {
            'filename': Path(file_path).name,
            'file_type': 'pdf',
            'parser': 'pdfplumber',
        }
        
        with pdfplumber.open(file_path) as pdf:
            doc_metadata['page_count'] = len(pdf.pages)
            
            if pdf.metadata:
                if pdf.metadata.get('Title'):
                    doc_metadata['title'] = pdf.metadata['Title']
                if pdf.metadata.get('Author'):
                    doc_metadata['author'] = pdf.metadata['Author']
            
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ''
                all_text.append(text)
                
                page_tables = page.extract_tables()
                if page_tables:
                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 1:
                            table_text = self._table_to_markdown(table)
                            tables.append({
                                'page_number': page_num + 1,
                                'table_index': table_idx,
                                'data': table,
                                'markdown': table_text,
                            })
                
                pages.append({
                    'page_number': page_num + 1,
                    'content': text,
                    'char_count': len(text),
                })
        
        content = '\n\n'.join(all_text)
        
        if tables:
            table_content = "\n\n## 表格内容\n\n"
            for t in tables:
                table_content += f"### 第{t['page_number']}页 表格{t['table_index'] + 1}\n\n"
                table_content += t['markdown'] + "\n\n"
            content = content + "\n\n" + table_content
        
        return ParsedDocument(
            content=content,
            doc_metadata=doc_metadata,
            pages=pages,
            tables=tables if tables else None,
        )
    
    def _table_to_markdown(self, table: List[List]) -> str:
        if not table or len(table) < 1:
            return ""
        
        md_lines = []
        
        header = table[0]
        header = [str(cell) if cell else '' for cell in header]
        md_lines.append('| ' + ' | '.join(header) + ' |')
        md_lines.append('| ' + ' | '.join(['---'] * len(header)) + ' |')
        
        for row in table[1:]:
            row = [str(cell).replace('\n', ' ') if cell else '' for cell in row]
            while len(row) < len(header):
                row.append('')
            md_lines.append('| ' + ' | '.join(row[:len(header)]) + ' |')
        
        return '\n'.join(md_lines)


@dataclass
class OCRLayoutBlock:
    """OCR版面分析块"""
    block_type: str
    content: str
    bbox: Tuple[float, float, float, float]
    confidence: float = 1.0
    page_number: int = 1
    children: List['OCRLayoutBlock'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRTableResult:
    """OCR表格识别结果"""
    page_number: int
    bbox: Tuple[float, float, float, float]
    html_content: str
    markdown_content: str
    rows: List[List[str]] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class OCRFormulaResult:
    """OCR公式识别结果"""
    page_number: int
    bbox: Tuple[float, float, float, float]
    latex: str
    confidence: float = 1.0


@dataclass
class OCRKeyValueResult:
    """OCR关键信息抽取结果"""
    key: str
    value: str
    key_bbox: Optional[Tuple[float, float, float, float]] = None
    value_bbox: Optional[Tuple[float, float, float, float]] = None
    page_number: int = 1
    confidence: float = 1.0


class OCRParser:
    """
    OCR解析器 - PaddleOCR集成
    
    核心能力：
    - PP-OCRv4: 文本检测与识别（80+语言）
    - PP-StructureV3: 版面分析、表格识别、公式识别
    - KIE: 关键信息抽取（SER + RE）
    - 方向分类: 自动纠正旋转文本
    - 多语言支持: 中英日韩等80+语言
    """
    
    LAYOUT_LABELS = {
        'text': '文本',
        'title': '标题',
        'figure': '图片',
        'figure_caption': '图片标题',
        'table': '表格',
        'table_caption': '表格标题',
        'header': '页眉',
        'footer': '页脚',
        'reference': '引用',
        'equation': '公式',
        'list': '列表',
    }
    
    def __init__(
        self,
        lang: str = 'ch',
        use_gpu: bool = False,
        use_angle_cls: bool = True,
        use_space_char: bool = True,
        det_db_thresh: float = 0.3,
        det_db_box_thresh: float = 0.5,
        det_db_unclip_ratio: float = 1.6,
        enable_layout: bool = True,
        enable_table: bool = True,
        enable_formula: bool = False,
        enable_kie: bool = False,
        table_char_dict_path: str = None,
        layout_model_dir: str = None,
        table_model_dir: str = None,
    ):
        self.lang = lang
        self.use_gpu = use_gpu
        self.use_angle_cls = use_angle_cls
        self.use_space_char = use_space_char
        self.det_db_thresh = det_db_thresh
        self.det_db_box_thresh = det_db_box_thresh
        self.det_db_unclip_ratio = det_db_unclip_ratio
        self.enable_layout = enable_layout
        self.enable_table = enable_table
        self.enable_formula = enable_formula
        self.enable_kie = enable_kie
        self.table_char_dict_path = table_char_dict_path
        self.layout_model_dir = layout_model_dir
        self.table_model_dir = table_model_dir
        
        self._ocr = None
        self._structure = None
        self._table_engine = None
        self._layout_engine = None
    
    def _check_installation(self) -> bool:
        try:
            import paddleocr
            return True
        except ImportError:
            return False
    
    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(
                    use_angle_cls=self.use_angle_cls,
                    lang=self.lang,
                    use_gpu=self.use_gpu,
                    show_log=False,
                    use_space_char=self.use_space_char,
                    det_db_thresh=self.det_db_thresh,
                    det_db_box_thresh=self.det_db_box_thresh,
                    det_db_unclip_ratio=self.det_db_unclip_ratio,
                )
            except ImportError:
                raise ImportError(
                    "PaddleOCR not installed. "
                    "Run: pip install paddleocr paddlepaddle"
                )
        return self._ocr
    
    def _get_structure_engine(self):
        if self._structure is None:
            try:
                from paddleocr import PPStructure
                
                self._structure = PPStructure(
                    use_angle_cls=self.use_angle_cls,
                    lang=self.lang,
                    use_gpu=self.use_gpu,
                    show_log=False,
                    layout=self.enable_layout,
                    table=self.enable_table,
                    ocr=True,
                )
            except ImportError:
                raise ImportError(
                    "PP-Structure not installed. "
                    "Run: pip install paddleocr paddlepaddle"
                )
        return self._structure
    
    def _get_table_engine(self):
        if self._table_engine is None:
            try:
                from paddleocr import PPStructure
                
                self._table_engine = PPStructure(
                    use_angle_cls=self.use_angle_cls,
                    lang=self.lang,
                    use_gpu=self.use_gpu,
                    show_log=False,
                    layout=False,
                    table=True,
                    ocr=True,
                )
            except ImportError:
                raise ImportError(
                    "PP-Structure not installed. "
                    "Run: pip install paddleocr paddlepaddle"
                )
        return self._table_engine
    
    def parse(self, file_path: str) -> ParsedDocument:
        if not self._check_installation():
            raise ImportError(
                "PaddleOCR not installed. "
                "Run: pip install paddleocr paddlepaddle"
            )
        
        import fitz
        
        ocr = self._get_ocr()
        
        doc = fitz.open(file_path)
        
        all_text = []
        pages = []
        doc_metadata = {
            'filename': Path(file_path).name,
            'file_type': 'pdf',
            'page_count': len(doc),
            'parser': 'ocr',
            'ocr_engine': 'paddleocr',
            'lang': self.lang,
            'use_gpu': self.use_gpu,
        }
        
        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            
            try:
                result = ocr.ocr(tmp_path, cls=True)
                
                page_text = []
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) >= 2:
                            text = line[1][0]
                            page_text.append(text)
                
                text = '\n'.join(page_text)
                all_text.append(text)
                
                pages.append({
                    'page_number': page_num + 1,
                    'content': text,
                    'char_count': len(text),
                })
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        
        doc.close()
        
        content = '\n\n'.join(all_text)
        
        return ParsedDocument(
            content=content,
            doc_metadata=doc_metadata,
            pages=pages,
        )
    
    def parse_with_layout(
        self,
        file_path: str,
    ) -> Tuple[ParsedDocument, List[OCRLayoutBlock]]:
        """
        解析PDF并返回版面分析结果
        """
        if not self._check_installation():
            raise ImportError("PaddleOCR not installed. Run: pip install paddleocr paddlepaddle")
        
        import fitz
        
        structure = self._get_structure_engine()
        doc = fitz.open(file_path)
        
        all_text = []
        pages = []
        all_layout_blocks = []
        
        doc_metadata = {
            'filename': Path(file_path).name,
            'file_type': 'pdf',
            'page_count': len(doc),
            'parser': 'ocr',
            'ocr_engine': 'paddleocr',
            'enable_layout': True,
        }
        
        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            
            try:
                result = structure(tmp_path)
                
                page_text = []
                for region in result:
                    region_type = region.get('type', 'text')
                    bbox = region.get('bbox', [0, 0, 0, 0])
                    
                    if region_type == 'table':
                        table_html = region.get('res', {}).get('html', '')
                        if table_html:
                            page_text.append(f"[表格]\n{table_html}")
                            
                            all_layout_blocks.append(OCRLayoutBlock(
                                block_type='table',
                                content=table_html,
                                bbox=tuple(bbox) if len(bbox) == 4 else (0, 0, 0, 0),
                                page_number=page_num + 1,
                                metadata={'html': table_html},
                            ))
                    else:
                        text_content = ""
                        if 'res' in region:
                            res_list = region['res']
                            if isinstance(res_list, list):
                                for item in res_list:
                                    if isinstance(item, dict) and 'text' in item:
                                        text_content += item['text'] + ' '
                            elif isinstance(res_list, str):
                                text_content = res_list
                        
                        if text_content:
                            page_text.append(text_content)
                            
                            all_layout_blocks.append(OCRLayoutBlock(
                                block_type=region_type,
                                content=text_content.strip(),
                                bbox=tuple(bbox) if len(bbox) == 4 else (0, 0, 0, 0),
                                page_number=page_num + 1,
                                metadata={'original_type': region_type},
                            ))
                
                text = '\n'.join(page_text)
                all_text.append(text)
                
                pages.append({
                    'page_number': page_num + 1,
                    'content': text,
                    'char_count': len(text),
                })
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        
        doc.close()
        
        content = '\n\n'.join(all_text)
        
        parsed_doc = ParsedDocument(
            content=content,
            doc_metadata=doc_metadata,
            pages=pages,
        )
        
        return parsed_doc, all_layout_blocks
    
    def extract_tables(
        self,
        file_path: str,
    ) -> List[OCRTableResult]:
        """
        提取表格
        """
        if not self._check_installation():
            raise ImportError("PaddleOCR not installed. Run: pip install paddleocr paddlepaddle")
        
        import fitz
        
        table_engine = self._get_table_engine()
        doc = fitz.open(file_path)
        
        tables = []
        
        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            
            try:
                result = table_engine(tmp_path)
                
                for region in result:
                    if region.get('type') == 'table':
                        bbox = region.get('bbox', [0, 0, 0, 0])
                        html_content = region.get('res', {}).get('html', '')
                        
                        rows = self._parse_html_table(html_content)
                        markdown = self._html_table_to_markdown(html_content)
                        
                        tables.append(OCRTableResult(
                            page_number=page_num + 1,
                            bbox=tuple(bbox) if len(bbox) == 4 else (0, 0, 0, 0),
                            html_content=html_content,
                            markdown_content=markdown,
                            rows=rows,
                        ))
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        
        doc.close()
        
        return tables
    
    def _parse_html_table(self, html: str) -> List[List[str]]:
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            rows = []
            
            for tr in soup.find_all('tr'):
                cells = []
                for td in tr.find_all(['td', 'th']):
                    cells.append(td.get_text(strip=True))
                if cells:
                    rows.append(cells)
            
            return rows
        except ImportError:
            return []
    
    def _html_table_to_markdown(self, html: str) -> str:
        rows = self._parse_html_table(html)
        if not rows:
            return ""
        
        md_lines = []
        
        header = rows[0]
        md_lines.append('| ' + ' | '.join(str(cell) for cell in header) + ' |')
        md_lines.append('| ' + ' | '.join(['---'] * len(header)) + ' |')
        
        for row in rows[1:]:
            while len(row) < len(header):
                row.append('')
            md_lines.append('| ' + ' | '.join(str(cell) for cell in row[:len(header)]) + ' |')
        
        return '\n'.join(md_lines)
    
    def semantic_chunking(
        self,
        file_path: str,
        max_chunk_size: int = 1000,
        respect_structure: bool = True,
    ) -> List[SemanticChunk]:
        """
        基于版面分析的语义分块
        """
        parsed_doc, layout_blocks = self.parse_with_layout(file_path)
        
        chunks = []
        current_chunk_content = []
        current_chunk_size = 0
        current_section_path = []
        current_page_numbers = set()
        chunk_id = 0
        
        for block in layout_blocks:
            block_content = block.content
            block_size = len(block_content)
            
            if block.block_type in ['title', 'header']:
                if current_chunk_content and current_chunk_size > 0:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content='\n'.join(current_chunk_content),
                        chunk_type='text',
                        page_numbers=sorted(list(current_page_numbers)),
                        section_path=current_section_path.copy(),
                        token_count=current_chunk_size // 4,
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                
                current_chunk_content = []
                current_chunk_size = 0
                current_page_numbers = set()
                
                title_text = block_content.strip('#').strip()
                current_section_path.append(title_text)
            
            elif block.block_type in ['text', 'list', 'reference']:
                if respect_structure and current_chunk_size + block_size > max_chunk_size:
                    if current_chunk_content:
                        chunk = SemanticChunk(
                            chunk_id=f"chunk_{chunk_id}",
                            content='\n'.join(current_chunk_content),
                            chunk_type='text',
                            page_numbers=sorted(list(current_page_numbers)),
                            section_path=current_section_path.copy(),
                            token_count=current_chunk_size // 4,
                        )
                        chunks.append(chunk)
                        chunk_id += 1
                    
                    current_chunk_content = []
                    current_chunk_size = 0
                    current_page_numbers = set()
                
                current_chunk_content.append(block_content)
                current_chunk_size += block_size
                current_page_numbers.add(block.page_number)
            
            elif block.block_type == 'table':
                if current_chunk_content:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content='\n'.join(current_chunk_content),
                        chunk_type='text',
                        page_numbers=sorted(list(current_page_numbers)),
                        section_path=current_section_path.copy(),
                        token_count=current_chunk_size // 4,
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                    
                    current_chunk_content = []
                    current_chunk_size = 0
                    current_page_numbers = set()
                
                if block_content:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content=block_content,
                        chunk_type='table',
                        page_numbers=[block.page_number],
                        section_path=current_section_path.copy(),
                        token_count=len(block_content) // 4,
                        metadata={'bbox': block.bbox},
                    )
                    chunks.append(chunk)
                    chunk_id += 1
        
        if current_chunk_content:
            chunk = SemanticChunk(
                chunk_id=f"chunk_{chunk_id}",
                content='\n'.join(current_chunk_content),
                chunk_type='text',
                page_numbers=sorted(list(current_page_numbers)),
                section_path=current_section_path.copy(),
                token_count=current_chunk_size // 4,
            )
            chunks.append(chunk)
        
        return chunks
    
    def ocr_image(
        self,
        image_path: str,
        cls: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        对单张图片进行OCR识别
        
        Returns:
            [{'text': str, 'confidence': float, 'bbox': [x1, y1, x2, y2]}]
        """
        ocr = self._get_ocr()
        result = ocr.ocr(image_path, cls=cls)
        
        texts = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    bbox = line[0]
                    text = line[1][0]
                    confidence = line[1][1]
                    
                    texts.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': bbox,
                    })
        
        return texts
    
    def detect_text_regions(
        self,
        image_path: str,
    ) -> List[Dict[str, Any]]:
        """
        检测文本区域（仅检测，不识别）
        """
        ocr = self._get_ocr()
        
        import cv2
        img = cv2.imread(image_path)
        
        result = ocr.ocr(image_path, det=True, rec=False, cls=False)
        
        regions = []
        if result and result[0]:
            for line in result[0]:
                if line:
                    bbox = line
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    
                    regions.append({
                        'bbox': [min(x_coords), min(y_coords), max(x_coords), max(y_coords)],
                        'polygon': bbox,
                    })
        
        return regions
    
    def recognize_text(
        self,
        image_path: str,
        det: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        识别文本（仅识别，不检测）
        
        Args:
            image_path: 图片路径（需为已裁剪的文本行图片）
            det: 是否进行检测
        """
        ocr = self._get_ocr()
        result = ocr.ocr(image_path, det=det, rec=True, cls=True)
        
        texts = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0]
                    confidence = line[1][1]
                    
                    texts.append({
                        'text': text,
                        'confidence': confidence,
                    })
        
        return texts
    
    def get_supported_languages(self) -> List[str]:
        """
        获取支持的语言列表
        """
        return [
            'ch', 'en', 'french', 'german', 'korean', 'japan',
            'chinese_cht', 'ta', 'te', 'ka', 'latin', 'arabic',
            'cyrillic', 'devanagari',
        ]
    
    def get_layout_labels(self) -> Dict[str, str]:
        """
        获取版面分析标签
        """
        return self.LAYOUT_LABELS.copy()


@dataclass
class DoclingLayoutBlock:
    """Docling版面分析块"""
    item_type: str
    content: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    page_number: int = 1
    label: str = ""
    parent_ref: Optional[str] = None
    children_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DoclingTableItem:
    """Docling表格项"""
    table_index: int
    page_number: int
    num_rows: int
    num_cols: int
    html_content: str
    markdown_content: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    caption: Optional[str] = None


@dataclass
class DoclingPictureItem:
    """Docling图片项"""
    picture_index: int
    page_number: int
    bbox: Optional[Tuple[float, float, float, float]] = None
    caption: Optional[str] = None
    image_data: Optional[bytes] = None


@dataclass
class DoclingKeyValueItem:
    """Docling键值对项"""
    key: str
    value: str
    page_number: int
    bbox: Optional[Tuple[float, float, float, float]] = None


class DoclingParser:
    """
    Docling解析器 - IBM开源深度文档解析
    
    核心能力：
    - 多格式支持：PDF, DOCX, PPTX, XLSX, HTML, 图片等
    - 高级PDF理解：页面布局、阅读顺序、表格结构
    - 公式识别、代码块识别
    - OCR支持（扫描件PDF和图片）
    - VLM支持（视觉语言模型）
    - 统一DoclingDocument格式
    - 多种导出：Markdown, HTML, JSON, DocTags
    """
    
    def __init__(
        self,
        enable_ocr: bool = True,
        enable_table_structure: bool = True,
        use_vlm: bool = False,
        vlm_model: str = "granite_docling",
        ocr_engine: str = "easyocr",
        export_format: str = "markdown",
    ):
        self.enable_ocr = enable_ocr
        self.enable_table_structure = enable_table_structure
        self.use_vlm = use_vlm
        self.vlm_model = vlm_model
        self.ocr_engine = ocr_engine
        self.export_format = export_format
        self._converter = None
    
    def _check_installation(self) -> bool:
        try:
            import docling
            return True
        except ImportError:
            return False
    
    def _get_converter(self):
        if self._converter is None:
            from docling.document_converter import DocumentConverter
            
            if self.use_vlm:
                from docling.pipeline.vlm_pipeline import VlmPipeline
                from docling.backends.pypdfium2_backend import PyPdfiumDocumentBackend
                
                self._converter = DocumentConverter(
                    pipeline=VlmPipeline(
                        vlm_model=self.vlm_model,
                    ),
                    backend=PyPdfiumDocumentBackend,
                )
            else:
                pipeline_options = self._get_pipeline_options()
                if pipeline_options:
                    from docling.pipeline.simple_pipeline import SimplePipeline
                    self._converter = DocumentConverter(
                        pipeline=SimplePipeline(pipeline_options),
                    )
                else:
                    self._converter = DocumentConverter()
        
        return self._converter
    
    def _get_pipeline_options(self):
        try:
            from docling.pipeline.simple_pipeline import SimplePipeline
            
            if self.enable_ocr:
                from docling.datamodel.pipeline_options import PipelineOptions
                from docling.datamodel.base_models import InputFormat
                from docling.pipeline.simple_pipeline import SimplePipeline
                
                pipeline_options = PipelineOptions(
                    do_ocr=True,
                    ocr_options=self._get_ocr_options(),
                )
                return pipeline_options
        except ImportError:
            pass
        return None
    
    def _get_ocr_options(self):
        try:
            if self.ocr_engine == "tesseract":
                from docling.datamodel.pipeline_options import TesseractOcrOptions
                return TesseractOcrOptions()
            else:
                from docling.datamodel.pipeline_options import EasyOcrOptions
                return EasyOcrOptions()
        except ImportError:
            return None
    
    def parse(self, file_path: str) -> ParsedDocument:
        if not self._check_installation():
            raise ImportError(
                "Docling not installed. "
                "Run: pip install docling"
            )
        
        converter = self._get_converter()
        result = converter.convert(file_path)
        
        doc = result.document
        
        doc_metadata = {
            'filename': Path(file_path).name,
            'file_type': Path(file_path).suffix.lower().lstrip('.'),
            'parser': 'docling',
            'enable_ocr': self.enable_ocr,
            'use_vlm': self.use_vlm,
        }
        
        if self.export_format == "markdown":
            content = doc.export_to_markdown()
        elif self.export_format == "html":
            content = doc.export_to_html()
        elif self.export_format == "json":
            import json
            content = json.dumps(doc.export_to_dict(), ensure_ascii=False, indent=2)
        else:
            content = doc.export_to_markdown()
        
        pages = self._extract_pages(doc)
        sections = self._extract_sections(doc)
        tables = self._extract_tables(doc)
        images = self._extract_pictures(doc)
        formulas = self._extract_formulas(doc)
        key_values = self._extract_key_values(doc)
        
        doc_metadata['page_count'] = len(pages)
        doc_metadata['table_count'] = len(tables) if tables else 0
        doc_metadata['image_count'] = len(images) if images else 0
        doc_metadata['formula_count'] = len(formulas) if formulas else 0
        
        return ParsedDocument(
            content=content,
            doc_metadata=doc_metadata,
            pages=pages if pages else None,
            sections=sections if sections else None,
            tables=tables if tables else None,
            images=images if images else None,
        )
    
    def _extract_pages(self, doc) -> List[Dict]:
        pages = []
        
        if hasattr(doc, 'pages'):
            for i, page in enumerate(doc.pages):
                page_content = ""
                if hasattr(page, 'text'):
                    page_content = page.text
                elif hasattr(page, 'content'):
                    page_content = str(page.content)
                
                pages.append({
                    'page_number': i + 1,
                    'content': page_content,
                    'char_count': len(page_content),
                })
        
        if not pages and hasattr(doc, 'texts'):
            page_texts = {}
            for text_item in doc.texts:
                if hasattr(text_item, 'prov') and text_item.prov:
                    for prov in text_item.prov:
                        page_no = prov.page if hasattr(prov, 'page') else 1
                        if page_no not in page_texts:
                            page_texts[page_no] = []
                        page_texts[page_no].append(text_item.text if hasattr(text_item, 'text') else str(text_item))
            
            for page_no in sorted(page_texts.keys()):
                content = '\n'.join(page_texts[page_no])
                pages.append({
                    'page_number': page_no,
                    'content': content,
                    'char_count': len(content),
                })
        
        return pages
    
    def _extract_sections(self, doc) -> List[Dict]:
        sections = []
        
        if hasattr(doc, 'texts'):
            for text_item in doc.texts:
                label = getattr(text_item, 'label', '')
                if label in ['section_header', 'title', 'heading']:
                    text = text_item.text if hasattr(text_item, 'text') else str(text_item)
                    level = getattr(text_item, 'level', 1)
                    
                    page_number = 1
                    if hasattr(text_item, 'prov') and text_item.prov:
                        page_number = text_item.prov[0].page if hasattr(text_item.prov[0], 'page') else 1
                    
                    sections.append({
                        'title': text,
                        'level': level,
                        'page_number': page_number,
                    })
        
        if hasattr(doc, 'body') and hasattr(doc.body, 'children'):
            self._extract_sections_from_tree(doc, doc.body, sections, [])
        
        return sections
    
    def _extract_sections_from_tree(self, doc, node, sections, path):
        if hasattr(node, 'children') and node.children:
            for child_ref in node.children:
                child = self._resolve_ref(doc, child_ref)
                if child:
                    label = getattr(child, 'label', '')
                    if label in ['section_header', 'title', 'heading']:
                        text = child.text if hasattr(child, 'text') else str(child)
                        level = getattr(child, 'level', len(path) + 1)
                        
                        page_number = 1
                        if hasattr(child, 'prov') and child.prov:
                            page_number = child.prov[0].page if hasattr(child.prov[0], 'page') else 1
                        
                        sections.append({
                            'title': text,
                            'level': level,
                            'page_number': page_number,
                        })
                    
                    self._extract_sections_from_tree(doc, child, sections, path)
    
    def _resolve_ref(self, doc, ref):
        if isinstance(ref, str):
            try:
                parts = ref.strip('#/').split('/')
                obj = doc
                for part in parts:
                    if part.isdigit():
                        obj = obj[int(part)]
                    else:
                        obj = getattr(obj, part, None)
                        if obj is None:
                            return None
                return obj
            except Exception:
                return None
        return ref
    
    def _extract_tables(self, doc) -> List[Dict]:
        tables = []
        
        if hasattr(doc, 'tables'):
            for i, table_item in enumerate(doc.tables):
                page_number = 1
                bbox = None
                
                if hasattr(table_item, 'prov') and table_item.prov:
                    prov = table_item.prov[0]
                    page_number = prov.page if hasattr(prov, 'page') else 1
                    if hasattr(prov, 'bbox'):
                        bbox_data = prov.bbox
                        if hasattr(bbox_data, 'l'):
                            bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                        elif isinstance(bbox_data, (list, tuple)) and len(bbox_data) >= 4:
                            bbox = tuple(bbox_data[:4])
                
                markdown_content = ""
                html_content = ""
                
                if hasattr(table_item, 'export_to_markdown'):
                    markdown_content = table_item.export_to_markdown()
                if hasattr(table_item, 'export_to_html'):
                    html_content = table_item.export_to_html()
                
                num_rows = 0
                num_cols = 0
                if hasattr(table_item, 'data') and table_item.data:
                    if hasattr(table_item.data, 'num_rows'):
                        num_rows = table_item.data.num_rows
                    if hasattr(table_item.data, 'num_cols'):
                        num_cols = table_item.data.num_cols
                
                tables.append({
                    'table_index': i,
                    'page_number': page_number,
                    'num_rows': num_rows,
                    'num_cols': num_cols,
                    'markdown': markdown_content,
                    'html': html_content,
                    'bbox': bbox,
                })
        
        return tables
    
    def _extract_pictures(self, doc) -> List[Dict]:
        pictures = []
        
        if hasattr(doc, 'pictures'):
            for i, pic_item in enumerate(doc.pictures):
                page_number = 1
                bbox = None
                
                if hasattr(pic_item, 'prov') and pic_item.prov:
                    prov = pic_item.prov[0]
                    page_number = prov.page if hasattr(prov, 'page') else 1
                    if hasattr(prov, 'bbox'):
                        bbox_data = prov.bbox
                        if hasattr(bbox_data, 'l'):
                            bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                
                caption = None
                if hasattr(pic_item, 'caption') and pic_item.caption:
                    caption = pic_item.caption.text if hasattr(pic_item.caption, 'text') else str(pic_item.caption)
                elif hasattr(pic_item, 'captions') and pic_item.captions:
                    caption = pic_item.captions[0].text if hasattr(pic_item.captions[0], 'text') else str(pic_item.captions[0])
                
                pictures.append({
                    'picture_index': i,
                    'page_number': page_number,
                    'bbox': bbox,
                    'caption': caption,
                })
        
        return pictures
    
    def _extract_formulas(self, doc) -> List[Dict]:
        formulas = []
        
        if hasattr(doc, 'texts'):
            for text_item in doc.texts:
                label = getattr(text_item, 'label', '')
                if label in ['formula', 'equation', 'math']:
                    text = text_item.text if hasattr(text_item, 'text') else str(text_item)
                    
                    page_number = 1
                    bbox = None
                    if hasattr(text_item, 'prov') and text_item.prov:
                        prov = text_item.prov[0]
                        page_number = prov.page if hasattr(prov, 'page') else 1
                        if hasattr(prov, 'bbox'):
                            bbox_data = prov.bbox
                            if hasattr(bbox_data, 'l'):
                                bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                    
                    formulas.append({
                        'latex': text,
                        'page_number': page_number,
                        'bbox': bbox,
                    })
        
        return formulas
    
    def _extract_key_values(self, doc) -> List[Dict]:
        key_values = []
        
        if hasattr(doc, 'key_value_items'):
            for kv_item in doc.key_value_items:
                key = ""
                value = ""
                
                if hasattr(kv_item, 'key'):
                    key = kv_item.key.text if hasattr(kv_item.key, 'text') else str(kv_item.key)
                if hasattr(kv_item, 'value'):
                    value = kv_item.value.text if hasattr(kv_item.value, 'text') else str(kv_item.value)
                
                page_number = 1
                bbox = None
                if hasattr(kv_item, 'prov') and kv_item.prov:
                    prov = kv_item.prov[0]
                    page_number = prov.page if hasattr(prov, 'page') else 1
                    if hasattr(prov, 'bbox'):
                        bbox_data = prov.bbox
                        if hasattr(bbox_data, 'l'):
                            bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                
                key_values.append({
                    'key': key,
                    'value': value,
                    'page_number': page_number,
                    'bbox': bbox,
                })
        
        return key_values
    
    def parse_with_layout(
        self,
        file_path: str,
    ) -> Tuple[ParsedDocument, List[DoclingLayoutBlock]]:
        """
        解析文档并返回版面分析结果
        """
        if not self._check_installation():
            raise ImportError("Docling not installed. Run: pip install docling")
        
        converter = self._get_converter()
        result = converter.convert(file_path)
        doc = result.document
        
        parsed_doc = self.parse(file_path)
        
        layout_blocks = self._extract_layout_blocks(doc)
        
        return parsed_doc, layout_blocks
    
    def _extract_layout_blocks(self, doc) -> List[DoclingLayoutBlock]:
        blocks = []
        
        if hasattr(doc, 'texts'):
            for text_item in doc.texts:
                label = getattr(text_item, 'label', 'paragraph')
                text = text_item.text if hasattr(text_item, 'text') else str(text_item)
                
                page_number = 1
                bbox = None
                if hasattr(text_item, 'prov') and text_item.prov:
                    prov = text_item.prov[0]
                    page_number = prov.page if hasattr(prov, 'page') else 1
                    if hasattr(prov, 'bbox'):
                        bbox_data = prov.bbox
                        if hasattr(bbox_data, 'l'):
                            bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                
                blocks.append(DoclingLayoutBlock(
                    item_type='text',
                    content=text,
                    bbox=bbox,
                    page_number=page_number,
                    label=label,
                    metadata={'original_label': label},
                ))
        
        if hasattr(doc, 'tables'):
            for table_item in doc.tables:
                page_number = 1
                bbox = None
                
                if hasattr(table_item, 'prov') and table_item.prov:
                    prov = table_item.prov[0]
                    page_number = prov.page if hasattr(prov, 'page') else 1
                    if hasattr(prov, 'bbox'):
                        bbox_data = prov.bbox
                        if hasattr(bbox_data, 'l'):
                            bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                
                markdown = ""
                if hasattr(table_item, 'export_to_markdown'):
                    markdown = table_item.export_to_markdown()
                
                blocks.append(DoclingLayoutBlock(
                    item_type='table',
                    content=markdown,
                    bbox=bbox,
                    page_number=page_number,
                    label='table',
                ))
        
        if hasattr(doc, 'pictures'):
            for pic_item in doc.pictures:
                page_number = 1
                bbox = None
                
                if hasattr(pic_item, 'prov') and pic_item.prov:
                    prov = pic_item.prov[0]
                    page_number = prov.page if hasattr(prov, 'page') else 1
                    if hasattr(prov, 'bbox'):
                        bbox_data = prov.bbox
                        if hasattr(bbox_data, 'l'):
                            bbox = (bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b)
                
                caption = ""
                if hasattr(pic_item, 'caption') and pic_item.caption:
                    caption = pic_item.caption.text if hasattr(pic_item.caption, 'text') else str(pic_item.caption)
                
                blocks.append(DoclingLayoutBlock(
                    item_type='picture',
                    content=caption,
                    bbox=bbox,
                    page_number=page_number,
                    label='picture',
                ))
        
        return blocks
    
    def semantic_chunking(
        self,
        file_path: str,
        max_chunk_size: int = 1000,
        respect_structure: bool = True,
    ) -> List[SemanticChunk]:
        """
        基于文档结构的语义分块
        """
        parsed_doc, layout_blocks = self.parse_with_layout(file_path)
        
        chunks = []
        current_chunk_content = []
        current_chunk_size = 0
        current_section_path = []
        current_page_numbers = set()
        chunk_id = 0
        
        for block in layout_blocks:
            block_content = block.content
            block_size = len(block_content)
            
            if block.label in ['section_header', 'title', 'heading']:
                if current_chunk_content and current_chunk_size > 0:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content='\n'.join(current_chunk_content),
                        chunk_type='text',
                        page_numbers=sorted(list(current_page_numbers)),
                        section_path=current_section_path.copy(),
                        token_count=current_chunk_size // 4,
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                
                current_chunk_content = []
                current_chunk_size = 0
                current_page_numbers = set()
                
                title_text = block_content.strip('#').strip()
                level = block.metadata.get('level', 1)
                
                while len(current_section_path) >= level:
                    current_section_path.pop()
                current_section_path.append(title_text)
            
            elif block.label in ['paragraph', 'text', 'list_item', 'code', 'formula']:
                if respect_structure and current_chunk_size + block_size > max_chunk_size:
                    if current_chunk_content:
                        chunk = SemanticChunk(
                            chunk_id=f"chunk_{chunk_id}",
                            content='\n'.join(current_chunk_content),
                            chunk_type='text',
                            page_numbers=sorted(list(current_page_numbers)),
                            section_path=current_section_path.copy(),
                            token_count=current_chunk_size // 4,
                        )
                        chunks.append(chunk)
                        chunk_id += 1
                    
                    current_chunk_content = []
                    current_chunk_size = 0
                    current_page_numbers = set()
                
                current_chunk_content.append(block_content)
                current_chunk_size += block_size
                current_page_numbers.add(block.page_number)
            
            elif block.label == 'table':
                if current_chunk_content:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content='\n'.join(current_chunk_content),
                        chunk_type='text',
                        page_numbers=sorted(list(current_page_numbers)),
                        section_path=current_section_path.copy(),
                        token_count=current_chunk_size // 4,
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                    
                    current_chunk_content = []
                    current_chunk_size = 0
                    current_page_numbers = set()
                
                if block_content:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content=block_content,
                        chunk_type='table',
                        page_numbers=[block.page_number],
                        section_path=current_section_path.copy(),
                        token_count=len(block_content) // 4,
                        metadata={'bbox': block.bbox},
                    )
                    chunks.append(chunk)
                    chunk_id += 1
        
        if current_chunk_content:
            chunk = SemanticChunk(
                chunk_id=f"chunk_{chunk_id}",
                content='\n'.join(current_chunk_content),
                chunk_type='text',
                page_numbers=sorted(list(current_page_numbers)),
                section_path=current_section_path.copy(),
                token_count=current_chunk_size // 4,
            )
            chunks.append(chunk)
        
        return chunks
    
    def export_to_json(self, file_path: str) -> Dict[str, Any]:
        """
        导出为DoclingDocument JSON格式（无损）
        """
        if not self._check_installation():
            raise ImportError("Docling not installed. Run: pip install docling")
        
        converter = self._get_converter()
        result = converter.convert(file_path)
        
        return result.document.export_to_dict()
    
    def export_to_html(self, file_path: str) -> str:
        """
        导出为HTML格式
        """
        if not self._check_installation():
            raise ImportError("Docling not installed. Run: pip install docling")
        
        converter = self._get_converter()
        result = converter.convert(file_path)
        
        return result.document.export_to_html()


class MinerUParser:
    """
    MinerU解析器 - 深度文档解析
    
    集成DeepDoc能力：
    - 版面分析 (Layout Analysis)
    - 表格结构识别 (Table Structure Recognition)
    - 公式识别 (Formula Recognition)
    - 多语言OCR (109种语言)
    - 阅读顺序重构
    - 语义分块
    """
    
    def __init__(
        self,
        backend: str = "hybrid",
        use_gpu: bool = True,
        languages: List[str] = None,
        extract_formulas: bool = True,
        extract_tables: bool = True,
        enable_ocr: bool = True,
    ):
        self.backend = backend
        self.use_gpu = use_gpu
        self.languages = languages or ['ch', 'en']
        self.extract_formulas = extract_formulas
        self.extract_tables = extract_tables
        self.enable_ocr = enable_ocr
        self._mineru = None
    
    def _check_installation(self):
        try:
            import magic_pdf
            return True
        except ImportError:
            return False
    
    def parse(self, file_path: str) -> ParsedDocument:
        if not self._check_installation():
            raise ImportError(
                "MinerU not installed. "
                "Run: pip install mineru[all]"
            )
        
        from magic_pdf.data.data_reader_writer import FileBasedDataReader
        from magic_pdf.data.dataset import PymuDocDataset
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
        
        doc_metadata = {
            'filename': Path(file_path).name,
            'file_type': 'pdf',
            'parser': 'mineru',
            'backend': self.backend,
        }
        
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(file_path)
        
        ds = PymuDocDataset(pdf_bytes)
        
        if ds.classify() == "ocr":
            infer_result = ds.apply_ocr()
        else:
            infer_result = ds.apply()
        
        content_list = infer_result.pipe_ocr_mode if hasattr(infer_result, 'pipe_ocr_mode') else []
        
        pages = []
        all_text = []
        tables = []
        sections = []
        images = []
        formulas = []
        
        page_number = 0
        current_section = None
        
        for item in content_list:
            item_type = item.get('type', 'text')
            
            if item_type == 'text':
                text = item.get('text', '')
                all_text.append(text)
                
                if item.get('page_number', 0) != page_number:
                    page_number = item.get('page_number', page_number + 1)
                    pages.append({
                        'page_number': page_number,
                        'content': '',
                        'char_count': 0,
                    })
                
                if pages:
                    pages[-1]['content'] += text + '\n'
                    pages[-1]['char_count'] += len(text)
            
            elif item_type == 'table':
                if self.extract_tables:
                    table_html = item.get('html', '')
                    table_md = item.get('markdown', '')
                    table_caption = item.get('caption', '')
                    
                    tables.append({
                        'page_number': item.get('page_number', page_number),
                        'html': table_html,
                        'markdown': table_md,
                        'caption': table_caption,
                        'bbox': item.get('bbox', []),
                    })
                    
                    if table_md:
                        all_text.append(f"\n[表格]\n{table_md}\n")
            
            elif item_type == 'image':
                image_caption = item.get('caption', '')
                images.append({
                    'page_number': item.get('page_number', page_number),
                    'caption': image_caption,
                    'bbox': item.get('bbox', []),
                })
                
                if image_caption:
                    all_text.append(f"\n[图片: {image_caption}]\n")
            
            elif item_type == 'equation':
                if self.extract_formulas:
                    latex = item.get('latex', '')
                    formulas.append({
                        'page_number': item.get('page_number', page_number),
                        'latex': latex,
                        'bbox': item.get('bbox', []),
                    })
                    
                    if latex:
                        all_text.append(f"\n$$\n{latex}\n$$\n")
            
            elif item_type == 'title':
                title_text = item.get('text', '')
                level = item.get('level', 1)
                
                sections.append({
                    'title': title_text,
                    'level': level,
                    'page_number': item.get('page_number', page_number),
                })
                
                all_text.append(f"\n{'#' * level} {title_text}\n")
                current_section = title_text
        
        content = '\n'.join(all_text)
        
        doc_metadata['page_count'] = len(pages)
        doc_metadata['table_count'] = len(tables)
        doc_metadata['image_count'] = len(images)
        doc_metadata['formula_count'] = len(formulas)
        doc_metadata['section_count'] = len(sections)
        
        return ParsedDocument(
            content=content,
            doc_metadata=doc_metadata,
            pages=pages,
            sections=sections if sections else None,
            tables=tables if tables else None,
            images=images if images else None,
        )
    
    def parse_with_layout(
        self,
        file_path: str,
    ) -> Tuple[ParsedDocument, List[LayoutBlock]]:
        """
        解析PDF并返回版面分析结果
        """
        if not self._check_installation():
            raise ImportError("MinerU not installed. Run: pip install mineru[all]")
        
        from magic_pdf.data.data_reader_writer import FileBasedDataReader
        from magic_pdf.data.dataset import PymuDocDataset
        
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(file_path)
        
        ds = PymuDocDataset(pdf_bytes)
        
        if ds.classify() == "ocr":
            infer_result = ds.apply_ocr()
        else:
            infer_result = ds.apply()
        
        layout_blocks = []
        
        for page_idx, page_info in enumerate(infer_result.get_pages_info()):
            blocks = page_info.get('blocks', [])
            
            for block in blocks:
                block_type = block.get('type', 'text')
                bbox = block.get('bbox', [0, 0, 0, 0])
                content = block.get('content', '')
                confidence = block.get('confidence', 1.0)
                
                layout_block = LayoutBlock(
                    block_type=block_type,
                    content=content,
                    bbox=tuple(bbox),
                    page_number=page_idx + 1,
                    confidence=confidence,
                    metadata=block,
                )
                layout_blocks.append(layout_block)
        
        parsed_doc = self.parse(file_path)
        
        return parsed_doc, layout_blocks
    
    def extract_tables_structured(
        self,
        file_path: str,
    ) -> List[TableStructure]:
        """
        提取结构化表格
        """
        if not self._check_installation():
            raise ImportError("MinerU not installed. Run: pip install mineru[all]")
        
        from magic_pdf.data.data_reader_writer import FileBasedDataReader
        from magic_pdf.data.dataset import PymuDocDataset
        
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(file_path)
        
        ds = PymuDocDataset(pdf_bytes)
        
        if ds.classify() == "ocr":
            infer_result = ds.apply_ocr()
        else:
            infer_result = ds.apply()
        
        tables = []
        
        for item in infer_result.pipe_ocr_mode:
            if item.get('type') == 'table':
                table = TableStructure(
                    page_number=item.get('page_number', 0),
                    bbox=tuple(item.get('bbox', [0, 0, 0, 0])),
                    html_content=item.get('html', ''),
                    markdown_content=item.get('markdown', ''),
                    caption=item.get('caption'),
                )
                tables.append(table)
        
        return tables
    
    def semantic_chunking(
        self,
        file_path: str,
        max_chunk_size: int = 1000,
        respect_structure: bool = True,
    ) -> List[SemanticChunk]:
        """
        基于文档结构的语义分块
        
        Args:
            file_path: PDF文件路径
            max_chunk_size: 最大分块大小
            respect_structure: 是否尊重文档结构边界
            
        Returns:
            语义分块列表
        """
        parsed_doc, layout_blocks = self.parse_with_layout(file_path)
        
        chunks = []
        current_chunk_content = []
        current_chunk_size = 0
        current_section_path = []
        current_page_numbers = set()
        chunk_id = 0
        
        for block in layout_blocks:
            block_content = block.content
            block_size = len(block_content)
            
            if block.block_type == 'title':
                if current_chunk_content and current_chunk_size > 0:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content='\n'.join(current_chunk_content),
                        chunk_type='text',
                        page_numbers=sorted(list(current_page_numbers)),
                        section_path=current_section_path.copy(),
                        token_count=current_chunk_size // 4,
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                
                current_chunk_content = []
                current_chunk_size = 0
                current_page_numbers = set()
                
                level = block.metadata.get('level', 1)
                title_text = block_content.strip('#').strip()
                
                while len(current_section_path) >= level:
                    current_section_path.pop()
                current_section_path.append(title_text)
            
            elif block.block_type in ['text', 'paragraph']:
                if respect_structure and current_chunk_size + block_size > max_chunk_size:
                    if current_chunk_content:
                        chunk = SemanticChunk(
                            chunk_id=f"chunk_{chunk_id}",
                            content='\n'.join(current_chunk_content),
                            chunk_type='text',
                            page_numbers=sorted(list(current_page_numbers)),
                            section_path=current_section_path.copy(),
                            token_count=current_chunk_size // 4,
                        )
                        chunks.append(chunk)
                        chunk_id += 1
                    
                    current_chunk_content = []
                    current_chunk_size = 0
                    current_page_numbers = set()
                
                current_chunk_content.append(block_content)
                current_chunk_size += block_size
                current_page_numbers.add(block.page_number)
            
            elif block.block_type == 'table':
                if current_chunk_content:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content='\n'.join(current_chunk_content),
                        chunk_type='text',
                        page_numbers=sorted(list(current_page_numbers)),
                        section_path=current_section_path.copy(),
                        token_count=current_chunk_size // 4,
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                    
                    current_chunk_content = []
                    current_chunk_size = 0
                    current_page_numbers = set()
                
                table_md = block.metadata.get('markdown', '')
                if table_md:
                    chunk = SemanticChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content=table_md,
                        chunk_type='table',
                        page_numbers=[block.page_number],
                        section_path=current_section_path.copy(),
                        token_count=len(table_md) // 4,
                        metadata={'bbox': block.bbox},
                    )
                    chunks.append(chunk)
                    chunk_id += 1
        
        if current_chunk_content:
            chunk = SemanticChunk(
                chunk_id=f"chunk_{chunk_id}",
                content='\n'.join(current_chunk_content),
                chunk_type='text',
                page_numbers=sorted(list(current_page_numbers)),
                section_path=current_section_path.copy(),
                token_count=current_chunk_size // 4,
            )
            chunks.append(chunk)
        
        return chunks


class PDFParser(DocumentParser):
    """
    PDF解析器主类（增强版）
    
    支持智能路由，根据文档特征自动选择最佳解析器
    
    解析器能力矩阵：
    | 解析器 | 文本 | 表格 | OCR | 公式 | 多栏 | 性能 |
    |--------|:----:|:----:|:---:|:----:|:----:|:----:|
    | pymupdf | ★★★★★ | ★☆☆☆☆ | ✗ | ✗ | ★☆☆☆☆ | ★★★★★ |
    | pdfplumber | ★★★★☆ | ★★★★★ | ✗ | ✗ | ★★☆☆☆ | ★★★★☆ |
    | ocr | ★★★☆☆ | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★★★☆ | ★★☆☆☆ |
    | docling | ★★★★☆ | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ | ★★★☆☆ |
    | mineru | ★★★★☆ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★☆☆☆ |
    
    智能路由策略：
    1. 扫描件 → OCR系解析器（按文件大小选择）
    2. 纯文本 → PyMuPDF（最快）
    3. 表格型 → PDFPlumber/MinerU（按复杂度选择）
    4. 公式 → MinerU
    5. 多栏 → Docling
    6. 混合型 → 综合判断
    """
    
    PARSER_TYPES = {
        "pymupdf": "快速文本提取，适用于文本型PDF",
        "pdfplumber": "表格提取，适用于包含表格的PDF",
        "ocr": "PaddleOCR深度解析（PP-OCRv4+PP-StructureV3版面分析+表格识别）",
        "docling": "IBM开源深度解析（多格式+OCR+VLM+版面分析）",
        "mineru": "MinerU深度解析（版面分析+表格识别+公式识别）",
    }
    
    def __init__(
        self,
        parser_type: str = "auto",
        fallback_order: List[str] = None,
        mineru_config: Dict[str, Any] = None,
        docling_config: Dict[str, Any] = None,
        ocr_config: Dict[str, Any] = None,
    ):
        self.parser_type = parser_type
        self.default_fallback_order = fallback_order
        self.mineru_config = mineru_config or {}
        self.docling_config = docling_config or {}
        self.ocr_config = ocr_config or {}
        self._parsers = {}
        self._analyzer = PDFFeatureAnalyzer()
    
    def _get_parser(self, parser_type: str):
        if parser_type not in self._parsers:
            if parser_type == "pymupdf":
                self._parsers[parser_type] = PyMuPDFParser()
            elif parser_type == "pdfplumber":
                self._parsers[parser_type] = PDFPlumberParser()
            elif parser_type == "ocr":
                self._parsers[parser_type] = OCRParser(**self.ocr_config)
            elif parser_type == "docling":
                self._parsers[parser_type] = DoclingParser(**self.docling_config)
            elif parser_type == "mineru":
                self._parsers[parser_type] = MinerUParser(**self.mineru_config)
            else:
                raise ValueError(f"Unknown parser type: {parser_type}. Available: pymupdf, pdfplumber, ocr, docling, mineru")
        
        return self._parsers[parser_type]
    
    async def parse(self, file_path: str) -> ParsedDocument:
        loop = asyncio.get_event_loop()
        
        parser_type = self.parser_type
        features = None
        
        if parser_type == "auto":
            features = await loop.run_in_executor(
                None, self._analyzer.analyze, file_path
            )
            parser_type = features.recommended_parser
            
            logger.info(
                f"Auto-selected parser: {parser_type} "
                f"(confidence: {features.confidence:.2f}, "
                f"complexity: {features.layout_complexity})"
            )
            
            if features.fallback_order:
                logger.debug(f"Dynamic fallback order: {features.fallback_order}")
        
        try:
            parser = self._get_parser(parser_type)
            result = await loop.run_in_executor(None, parser.parse, file_path)
            
            if features:
                result.doc_metadata['auto_routed'] = True
                result.doc_metadata['recommended_parser'] = parser_type
                result.doc_metadata['routing_confidence'] = features.confidence
                result.doc_metadata['layout_complexity'] = features.layout_complexity
                result.doc_metadata['document_features'] = {
                    'has_text_layer': features.has_text_layer,
                    'has_images': features.has_images,
                    'has_tables': features.has_tables,
                    'table_count': features.table_count,
                    'has_formulas': features.has_formulas,
                    'has_multi_column': features.has_multi_column,
                    'is_scanned': features.is_scanned,
                    'language': features.language,
                }
            
            return result
            
        except ImportError as e:
            logger.warning(f"Parser {parser_type} not available: {e}")
            
            fallback_order = (
                features.fallback_order 
                if features and features.fallback_order 
                else (self.default_fallback_order or ["pymupdf", "pdfplumber", "docling", "mineru", "ocr"])
            )
            
            for fallback_type in fallback_order:
                if fallback_type == parser_type:
                    continue
                try:
                    parser = self._get_parser(fallback_type)
                    result = await loop.run_in_executor(None, parser.parse, file_path)
                    result.doc_metadata['fallback_parser'] = fallback_type
                    result.doc_metadata['fallback_reason'] = str(e)
                    logger.info(f"Using fallback parser: {fallback_type}")
                    return result
                except ImportError as fallback_error:
                    logger.debug(f"Fallback {fallback_type} also unavailable: {fallback_error}")
                    continue
                except Exception as parse_error:
                    logger.warning(f"Fallback {fallback_type} failed: {parse_error}")
                    continue
            
            raise ImportError(
                f"No PDF parser available. "
                f"Install at least one: pip install PyMuPDF pdfplumber paddleocr mineru[all] docling"
            )
    
    def supported_extensions(self) -> List[str]:
        return ['.pdf']
    
    async def analyze(self, file_path: str) -> DocumentFeatures:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._analyzer.analyze, file_path
        )
    
    async def parse_with_layout(
        self,
        file_path: str,
        parser_type: str = "mineru",
    ) -> Tuple[ParsedDocument, List]:
        """
        解析PDF并返回版面分析结果
        
        Args:
            file_path: PDF文件路径
            parser_type: 使用的解析器 ("mineru", "docling" 或 "ocr")
        
        Returns:
            (ParsedDocument, layout_blocks)
        """
        parser = self._get_parser(parser_type)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, parser.parse_with_layout, file_path
        )
    
    async def extract_tables_structured(
        self,
        file_path: str,
        parser_type: str = "mineru",
    ) -> List:
        """
        提取结构化表格
        
        Args:
            file_path: PDF文件路径
            parser_type: 使用的解析器 ("mineru", "docling" 或 "ocr")
        
        Returns:
            表格结构列表
        """
        parser = self._get_parser(parser_type)
        loop = asyncio.get_event_loop()
        
        if parser_type == "mineru":
            return await loop.run_in_executor(
                None, parser.extract_tables_structured, file_path
            )
        elif parser_type == "ocr":
            return await loop.run_in_executor(
                None, parser.extract_tables, file_path
            )
        else:
            parsed_doc = await loop.run_in_executor(None, parser.parse, file_path)
            return parsed_doc.tables if parsed_doc.tables else []
    
    async def semantic_chunking(
        self,
        file_path: str,
        max_chunk_size: int = 1000,
        respect_structure: bool = True,
        parser_type: str = "mineru",
    ) -> List[SemanticChunk]:
        """
        基于文档结构的语义分块
        
        Args:
            file_path: PDF文件路径
            max_chunk_size: 最大分块大小
            respect_structure: 是否尊重文档结构边界
            parser_type: 使用的解析器 ("mineru", "docling" 或 "ocr")
        
        Returns:
            语义分块列表
        """
        parser = self._get_parser(parser_type)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, parser.semantic_chunking, file_path, max_chunk_size, respect_structure
        )
    
    async def ocr_image(
        self,
        image_path: str,
        cls: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        对单张图片进行OCR识别
        
        仅OCR解析器支持
        """
        parser = self._get_parser("ocr")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, parser.ocr_image, image_path, cls
        )
    
    async def detect_text_regions(
        self,
        image_path: str,
    ) -> List[Dict[str, Any]]:
        """
        检测文本区域（仅检测，不识别）
        
        仅OCR解析器支持
        """
        parser = self._get_parser("ocr")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, parser.detect_text_regions, image_path
        )
    
    async def export_to_json(
        self,
        file_path: str,
        parser_type: str = "docling",
    ) -> Dict[str, Any]:
        """
        导出为JSON格式（无损）
        
        仅Docling支持
        """
        parser = self._get_parser(parser_type)
        loop = asyncio.get_event_loop()
        
        if hasattr(parser, 'export_to_json'):
            return await loop.run_in_executor(
                None, parser.export_to_json, file_path
            )
        else:
            raise NotImplementedError(f"Parser {parser_type} does not support JSON export")
    
    async def export_to_html(
        self,
        file_path: str,
        parser_type: str = "docling",
    ) -> str:
        """
        导出为HTML格式
        
        仅Docling支持
        """
        parser = self._get_parser(parser_type)
        loop = asyncio.get_event_loop()
        
        if hasattr(parser, 'export_to_html'):
            return await loop.run_in_executor(
                None, parser.export_to_html, file_path
            )
        else:
            raise NotImplementedError(f"Parser {parser_type} does not support HTML export")
    
    def get_available_parsers(self) -> Dict[str, str]:
        available = {}
        for parser_type, desc in self.PARSER_TYPES.items():
            try:
                self._get_parser(parser_type)
                available[parser_type] = desc
            except ImportError:
                pass
        return available
