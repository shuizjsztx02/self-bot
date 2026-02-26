# PDF路由策略优化方案

## 一、当前问题总结

### 1.1 解析器推荐问题

| 问题类型 | 具体问题 | 影响 |
|----------|----------|------|
| 过度依赖MinerU | 多种场景都推荐mineru | 简单文档解析效率低 |
| OCRParser未使用 | 推荐逻辑中从未返回"ocr" | PP-Structure能力浪费 |
| pdfplumber未利用 | 有表格时不单独推荐pdfplumber | 表格提取可能不够精确 |
| Docling未独立推荐 | VLM能力未充分利用 | 复杂布局处理不佳 |

### 1.2 特征分析问题

| 问题类型 | 具体问题 | 影响 |
|----------|----------|------|
| 采样不足 | 仅采样前5页 | 大型文档特征遗漏 |
| 表格检测范围 | 仅检测前3页 | 后续表格被忽略 |
| 缺少公式检测 | 未实现 | 学术论文解析不完整 |
| 缺少多栏检测 | 未实现 | 报纸/杂志布局错误 |
| 语言检测未实现 | language="unknown" | OCR语言选择不优 |

### 1.3 回退策略问题

- 固定回退顺序，不考虑文档特征
- 没有性能优先级考量

## 二、优化方案

### 2.1 分层路由策略

```
┌─────────────────────────────────────────────────────────────────┐
│                        PDF文档输入                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   第一层：快速特征检测                            │
│  - 文件大小、页数、元数据                                        │
│  - 文本层存在性（1页采样）                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │  有文本层？      │             │  无文本层       │
    │  (文本型PDF)    │             │  (扫描件/图片)  │
    └─────────────────┘             └─────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│   第二层：深度特征分析        │   │   直接路由到OCR系解析器      │
│  - 表格检测（全文档采样）     │   │  - 小文件 → OCRParser       │
│  - 图片/图表检测             │   │  - 大文件 → MinerU          │
│  - 公式检测                  │   │  - 复杂布局 → Docling(VLM)  │
│  - 多栏布局检测              │   └─────────────────────────────┘
│  - 语言检测                  │
└─────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    第三层：智能路由决策                           │
│  根据特征组合选择最优解析器                                      │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    第四层：解析执行与回退                         │
│  - 执行解析                                                     │
│  - 失败时按特征动态回退                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 优化后的解析器推荐逻辑

```python
def _recommend_parser_v2(self, features: DocumentFeatures) -> Tuple[str, float]:
    """
    优化后的解析器推荐逻辑
    
    决策树：
    1. 扫描件/图片型 → OCR系解析器
    2. 有文本层 → 根据复杂度选择
    3. 混合型 → 综合判断
    """
    
    # === 第一优先级：扫描件/图片型PDF ===
    if features.is_scanned:
        # 根据文件大小和复杂度选择OCR解析器
        if features.page_count > 50:
            return ("mineru", 0.95)  # 大型扫描件用MinerU
        elif features.layout_complexity == "complex":
            return ("docling", 0.90)  # 复杂布局用Docling(VLM)
        else:
            return ("ocr", 0.90)  # 普通扫描件用OCRParser
    
    # === 第二优先级：纯文本型PDF ===
    if features.has_text_layer and not features.has_images and not features.has_tables:
        return ("pymupdf", 0.98)  # 纯文本，最快
    
    # === 第三优先级：表格型PDF ===
    if features.has_tables:
        # 表格数量多且布局简单 → pdfplumber
        if features.table_ratio > 0.3 and features.layout_complexity == "simple":
            return ("pdfplumber", 0.92)
        # 表格+复杂布局 → MinerU
        elif features.layout_complexity in ["medium", "complex"]:
            return ("mineru", 0.90)
        # 表格+图片 → 综合解析
        elif features.has_images:
            return ("mineru", 0.88)
        else:
            return ("pdfplumber", 0.85)
    
    # === 第四优先级：图文混合型 ===
    if features.has_images and features.has_text_layer:
        if features.image_ratio > 0.5:
            # 图片为主，需要OCR补充
            return ("ocr", 0.85)
        elif features.layout_complexity == "complex":
            return ("docling", 0.85)
        else:
            return ("pymupdf", 0.80)  # 文本为主，图片可忽略
    
    # === 第五优先级：有公式 ===
    if features.has_formulas:
        return ("mineru", 0.90)  # MinerU对公式支持较好
    
    # === 第六优先级：多栏布局 ===
    if features.has_multi_column:
        return ("docling", 0.85)  # Docling对多栏处理较好
    
    # === 默认：简单文本PDF ===
    if features.has_text_layer:
        return ("pymupdf", 0.90)
    
    # === 兜底 ===
    return ("pymupdf", 0.70)
```

### 2.3 优化后的特征分析

```python
@dataclass
class DocumentFeaturesV2:
    """增强的文档特征"""
    # 基础特征
    page_count: int = 0
    file_size: int = 0  # 新增：文件大小
    
    # 文本特征
    has_text_layer: bool = False
    text_density: float = 0.0
    language: str = "unknown"  # 实际检测
    
    # 图像特征
    has_images: bool = False
    image_ratio: float = 0.0
    is_scanned: bool = False
    
    # 表格特征
    has_tables: bool = False
    table_count: int = 0  # 新增：表格数量
    table_ratio: float = 0.0
    
    # 新增特征
    has_formulas: bool = False      # 公式检测
    has_multi_column: bool = False  # 多栏布局
    has_code_blocks: bool = False   # 代码块
    has_charts: bool = False        # 图表
    
    # 复杂度评估
    layout_complexity: str = "simple"
    
    # 推荐
    recommended_parser: str = "pymupdf"
    confidence: float = 0.0
    
    # 动态回退顺序
    fallback_order: List[str] = field(default_factory=list)


class PDFFeatureAnalyzerV2:
    """增强的PDF特征分析器"""
    
    def analyze(self, file_path: str, sample_pages: int = None) -> DocumentFeaturesV2:
        """
        智能采样分析
        
        - 小文件(<10页)：全量分析
        - 中等文件(10-50页)：采样20%页数
        - 大文件(>50页)：采样10%页数，最少10页
        """
        import fitz
        import os
        
        doc = fitz.open(file_path)
        page_count = len(doc)
        file_size = os.path.getsize(file_path)
        
        # 动态计算采样页数
        if sample_pages is None:
            if page_count <= 10:
                sample_pages = page_count
            elif page_count <= 50:
                sample_pages = max(10, page_count // 5)
            else:
                sample_pages = max(10, page_count // 10)
        
        features = DocumentFeaturesV2(
            page_count=page_count,
            file_size=file_size
        )
        
        # ... 详细分析逻辑
        
        return features
    
    def _detect_formulas(self, page) -> bool:
        """检测数学公式"""
        # 方法1：检测特殊字符模式
        text = page.get_text()
        formula_patterns = ['∑', '∫', '∂', '√', 'π', 'α', 'β', 'γ', '→', '∈']
        for pattern in formula_patterns:
            if pattern in text:
                return True
        
        # 方法2：检测LaTeX残留
        latex_patterns = ['\\frac', '\\sqrt', '\\sum', '\\int', '\\begin{equation}']
        for pattern in latex_patterns:
            if pattern in text:
                return True
        
        return False
    
    def _detect_multi_column(self, page) -> bool:
        """检测多栏布局"""
        blocks = page.get_text("dict").get("blocks", [])
        
        if len(blocks) < 2:
            return False
        
        # 获取所有文本块的x坐标
        text_blocks = [b for b in blocks if b.get('type') == 0]
        if len(text_blocks) < 3:
            return False
        
        # 分析x坐标分布
        x_positions = []
        for block in text_blocks:
            bbox = block.get('bbox', (0, 0, 0, 0))
            x_positions.append(bbox[0])
        
        # 如果有明显的两组x坐标，说明是多栏
        from collections import Counter
        x_groups = Counter(round(x / 50) for x in x_positions)
        
        return len([c for c in x_groups.values() if c >= 2]) >= 2
    
    def _detect_language(self, text: str) -> str:
        """检测文档语言"""
        # 简单规则检测
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text)
        
        if chinese_chars / max(total_chars, 1) > 0.3:
            return "zh"
        return "en"
```

### 2.4 动态回退策略

```python
def _get_dynamic_fallback_order(self, features: DocumentFeaturesV2) -> List[str]:
    """
    根据文档特征动态生成回退顺序
    """
    base_order = []
    
    # 根据文档类型确定优先级
    if features.is_scanned:
        # 扫描件：OCR系优先
        base_order = ["ocr", "mineru", "docling", "pymupdf"]
    elif features.has_tables:
        # 表格型：表格解析器优先
        base_order = ["pdfplumber", "mineru", "docling", "pymupdf"]
    elif features.layout_complexity == "complex":
        # 复杂布局：深度解析器优先
        base_order = ["docling", "mineru", "ocr", "pymupdf"]
    else:
        # 简单文档：轻量级优先
        base_order = ["pymupdf", "pdfplumber", "docling", "mineru"]
    
    return base_order
```

### 2.5 解析器能力矩阵

| 解析器 | 文本提取 | 表格识别 | OCR | 公式 | 版面分析 | 性能 | 适用场景 |
|--------|:--------:|:--------:|:---:|:----:|:--------:|:----:|----------|
| **PyMuPDF** | ★★★★★ | ★☆☆☆☆ | ✗ | ✗ | ★☆☆☆☆ | ★★★★★ | 纯文本PDF |
| **PDFPlumber** | ★★★★☆ | ★★★★★ | ✗ | ✗ | ★★☆☆☆ | ★★★★☆ | 表格型PDF |
| **OCRParser** | ★★★☆☆ | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★★★☆ | ★★☆☆☆ | 扫描件/图片 |
| **Docling** | ★★★★☆ | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ | ★★★☆☆ | 复杂布局 |
| **MinerU** | ★★★★☆ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★☆☆☆ | 学术论文/综合 |

## 三、实施建议

### 3.1 短期优化（低风险）

1. **修改推荐逻辑**：增加OCRParser和pdfplumber的推荐场景
2. **动态回退顺序**：根据文档特征调整回退优先级
3. **增加表格检测范围**：从3页扩展到全文档采样

### 3.2 中期优化（中风险）

1. **增强特征分析**：添加公式、多栏、语言检测
2. **智能采样策略**：根据文件大小动态调整采样比例
3. **性能监控**：记录各解析器的解析时间和质量

### 3.3 长期优化（高价值）

1. **机器学习路由**：基于历史数据训练路由模型
2. **混合解析**：同一文档不同区域使用不同解析器
3. **增量解析**：大文件分批解析，支持断点续传

## 四、性能对比预估

| 场景 | 当前策略 | 优化后策略 | 性能提升 |
|------|----------|------------|----------|
| 纯文本PDF(10页) | mineru(30s) | pymupdf(0.5s) | **60x** |
| 表格型PDF(简单) | mineru(25s) | pdfplumber(3s) | **8x** |
| 扫描件(小) | mineru(20s) | ocr(15s) | **1.3x** |
| 复杂布局 | mineru(30s) | docling(25s) | **1.2x** |
| 学术论文 | mineru(35s) | mineru(35s) | - |
