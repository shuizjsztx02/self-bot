from typing import List, Dict, Any, Optional
import re
from pathlib import Path

from .base import DocumentParser, ParsedDocument, ChunkResult


class MarkdownParser(DocumentParser):
    
    async def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata = self._extract_metadata(content, path)
        sections = self._extract_sections(content)
        
        clean_content = self._clean_content(content)
        
        return ParsedDocument(
            content=clean_content,
            metadata=metadata,
            sections=sections,
        )
    
    def supported_extensions(self) -> List[str]:
        return ['.md', '.markdown']
    
    def _extract_metadata(self, content: str, path: Path) -> Dict[str, Any]:
        metadata = {
            'filename': path.name,
            'file_type': 'markdown',
        }
        
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            for line in frontmatter.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip().strip('"\'')
        
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1)
        
        return metadata
    
    def _extract_sections(self, content: str) -> List[Dict]:
        sections = []
        lines = content.split('\n')
        
        current_section = None
        current_content = []
        
        for line in lines:
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if header_match:
                if current_section:
                    current_section['content'] = '\n'.join(current_content).strip()
                    sections.append(current_section)
                
                level = len(header_match.group(1))
                title = header_match.group(2)
                
                current_section = {
                    'level': level,
                    'title': title,
                    'content': '',
                }
                current_content = []
            else:
                current_content.append(line)
        
        if current_section:
            current_section['content'] = '\n'.join(current_content).strip()
            sections.append(current_section)
        
        return sections
    
    def _clean_content(self, content: str) -> str:
        content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        content = re.sub(r'```[\s\S]*?```', lambda m: m.group(0), content)
        content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '[图片: \\1]', content)
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', '\\1', content)
        content = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', '\\1', content)
        content = re.sub(r'~~([^~]+)~~', '\\1', content)
        
        return content.strip()
    
    def chunk_with_sections(
        self,
        parsed_doc: ParsedDocument,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[ChunkResult]:
        chunks = []
        
        if parsed_doc.sections:
            for section in parsed_doc.sections:
                section_content = f"## {section['title']}\n\n{section['content']}"
                
                if len(section_content) <= chunk_size:
                    chunks.append(ChunkResult(
                        content=section_content,
                        token_count=self.count_tokens(section_content),
                        section_title=section['title'],
                        metadata={'level': section['level']},
                    ))
                else:
                    text_chunks = self.chunk_text(section_content, chunk_size, overlap)
                    for i, chunk in enumerate(text_chunks):
                        chunks.append(ChunkResult(
                            content=chunk,
                            token_count=self.count_tokens(chunk),
                            section_title=section['title'],
                            metadata={
                                'level': section['level'],
                                'chunk_index': i,
                            },
                        ))
        else:
            text_chunks = self.chunk_text(parsed_doc.content, chunk_size, overlap)
            for i, chunk in enumerate(text_chunks):
                chunks.append(ChunkResult(
                    content=chunk,
                    token_count=self.count_tokens(chunk),
                    metadata={'chunk_index': i},
                ))
        
        return chunks
