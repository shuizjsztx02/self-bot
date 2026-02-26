from typing import List, Dict, Any, Optional
from pathlib import Path

from .base import DocumentParser, ParsedDocument, ChunkResult


class TXTParser(DocumentParser):
    
    async def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata = {
            'filename': path.name,
            'file_type': 'txt',
            'char_count': len(content),
            'line_count': content.count('\n') + 1,
        }
        
        first_line = content.split('\n')[0].strip()
        if first_line and len(first_line) < 100:
            metadata['title'] = first_line
        
        return ParsedDocument(
            content=content.strip(),
            metadata=metadata,
        )
    
    def supported_extensions(self) -> List[str]:
        return ['.txt']
    
    def chunk_with_paragraphs(
        self,
        parsed_doc: ParsedDocument,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[ChunkResult]:
        chunks = []
        
        paragraphs = parsed_doc.content.split('\n\n')
        
        current_chunk = ""
        current_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += ('\n\n' if current_chunk else '') + para
                current_paragraphs.append(para)
            else:
                if current_chunk:
                    chunks.append(ChunkResult(
                        content=current_chunk,
                        token_count=self.count_tokens(current_chunk),
                        metadata={'paragraph_count': len(current_paragraphs)},
                    ))
                
                if len(para) > chunk_size:
                    text_chunks = self.chunk_text(para, chunk_size, overlap)
                    for i, chunk in enumerate(text_chunks):
                        chunks.append(ChunkResult(
                            content=chunk,
                            token_count=self.count_tokens(chunk),
                            metadata={'chunk_index': i, 'long_paragraph': True},
                        ))
                    current_chunk = ""
                    current_paragraphs = []
                else:
                    current_chunk = para
                    current_paragraphs = [para]
        
        if current_chunk:
            chunks.append(ChunkResult(
                content=current_chunk,
                token_count=self.count_tokens(current_chunk),
                metadata={'paragraph_count': len(current_paragraphs)},
            ))
        
        return chunks
