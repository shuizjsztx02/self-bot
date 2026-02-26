"""
BM25 检索器实现
用于关键词检索，与向量检索配合实现混合检索
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import asyncio
import logging
import re
import math
import json
import os
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BM25Document:
    """BM25 文档"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)


@dataclass
class BM25Config:
    """BM25 配置"""
    k1: float = 1.5
    b: float = 0.75
    epsilon: float = 0.25


class BM25Index:
    """
    BM25 索引
    
    使用 Okapi BM25 算法进行关键词检索
    支持中英文分词
    支持持久化到磁盘
    """
    
    def __init__(self, config: Optional[BM25Config] = None, persist_path: Optional[str] = None):
        self.config = config or BM25Config()
        self.documents: Dict[str, BM25Document] = {}
        self.doc_freqs: Dict[str, int] = {}
        self.doc_len: Dict[str, int] = {}
        self.avgdl: float = 0
        self.n_docs: int = 0
        self._idf_cache: Dict[str, float] = {}
        self.persist_path = persist_path
        
        if persist_path and os.path.exists(persist_path):
            self._load_from_disk()
    
    def _tokenize(self, text: str) -> List[str]:
        """
        分词函数
        支持中英文混合文本
        """
        text = text.lower()
        
        chinese_pattern = r'[\u4e00-\u9fff]+'
        english_pattern = r'[a-z0-9]+'
        
        chinese_chars = re.findall(chinese_pattern, text)
        chinese_tokens = []
        for chars in chinese_chars:
            chinese_tokens.extend(list(chars))
        
        english_tokens = re.findall(english_pattern, text)
        
        tokens = chinese_tokens + english_tokens
        
        tokens = [t for t in tokens if len(t) > 0]
        
        return tokens
    
    def _compute_idf(self, word: str) -> float:
        """计算 IDF 值"""
        if word in self._idf_cache:
            return self._idf_cache[word]
        
        n = self.doc_freqs.get(word, 0)
        if n == 0:
            idf = math.log((self.n_docs + 0.5) / 0.5)
        else:
            idf = math.log((self.n_docs - n + 0.5) / (n + 0.5) + 1)
        
        self._idf_cache[word] = idf
        return idf
    
    def _score_document(self, query_tokens: List[str], doc: BM25Document) -> float:
        """计算文档与查询的 BM25 分数"""
        score = 0.0
        doc_tokens = doc.tokens
        doc_len = len(doc_tokens)
        
        tf = Counter(doc_tokens)
        
        for term in query_tokens:
            if term not in tf:
                continue
            
            idf = self._compute_idf(term)
            term_freq = tf[term]
            
            numerator = term_freq * (self.config.k1 + 1)
            denominator = term_freq + self.config.k1 * (
                1 - self.config.b + self.config.b * doc_len / self.avgdl
            )
            
            score += idf * numerator / denominator
        
        return score
    
    def add_documents(self, documents: List[BM25Document]) -> None:
        """添加文档到索引"""
        for doc in documents:
            if doc.id in self.documents:
                continue
            
            doc.tokens = self._tokenize(doc.content)
            self.documents[doc.id] = doc
            self.doc_len[doc.id] = len(doc.tokens)
            
            term_set = set(doc.tokens)
            for term in term_set:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
            
            self.n_docs += 1
        
        if self.n_docs > 0:
            self.avgdl = sum(self.doc_len.values()) / self.n_docs
        
        self._idf_cache.clear()
        
        logger.info(f"BM25 index updated: {self.n_docs} documents, avg length: {self.avgdl:.2f}")
        
        self.save_to_disk()
    
    def remove_documents(self, doc_ids: List[str]) -> None:
        """从索引中移除文档"""
        for doc_id in doc_ids:
            if doc_id not in self.documents:
                continue
            
            doc = self.documents[doc_id]
            term_set = set(doc.tokens)
            for term in term_set:
                if term in self.doc_freqs:
                    self.doc_freqs[term] -= 1
                    if self.doc_freqs[term] <= 0:
                        del self.doc_freqs[term]
            
            del self.documents[doc_id]
            del self.doc_len[doc_id]
            self.n_docs -= 1
        
        if self.n_docs > 0:
            self.avgdl = sum(self.doc_len.values()) / self.n_docs
        else:
            self.avgdl = 0
        
        self._idf_cache.clear()
        
        self.save_to_disk()
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[BM25Document, float]]:
        """
        搜索文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大文档数
            min_score: 最小分数阈值
        
        Returns:
            List of (document, score) tuples
        """
        if not self.documents:
            return []
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        scores = []
        for doc_id, doc in self.documents.items():
            score = self._score_document(query_tokens, doc)
            if score >= min_score:
                scores.append((doc, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]
    
    def clear(self) -> None:
        """清空索引"""
        self.documents.clear()
        self.doc_freqs.clear()
        self.doc_len.clear()
        self._idf_cache.clear()
        self.n_docs = 0
        self.avgdl = 0
        
        if self.persist_path and os.path.exists(self.persist_path):
            try:
                os.remove(self.persist_path)
                logger.info(f"BM25 index file removed: {self.persist_path}")
            except Exception as e:
                logger.warning(f"Failed to remove BM25 index file: {e}")

    def save_to_disk(self) -> None:
        """保存索引到磁盘"""
        if not self.persist_path:
            return
        
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            
            data = {
                'config': asdict(self.config),
                'documents': {
                    doc_id: {
                        'id': doc.id,
                        'content': doc.content,
                        'metadata': doc.metadata,
                        'tokens': doc.tokens,
                    }
                    for doc_id, doc in self.documents.items()
                },
                'doc_freqs': self.doc_freqs,
                'doc_len': self.doc_len,
                'avgdl': self.avgdl,
                'n_docs': self.n_docs,
            }
            
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"BM25 index saved to {self.persist_path}: {self.n_docs} documents")
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")

    def _load_from_disk(self) -> None:
        """从磁盘加载索引"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        
        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.config = BM25Config(**data.get('config', {}))
            self.documents = {
                doc_id: BM25Document(**doc_data)
                for doc_id, doc_data in data.get('documents', {}).items()
            }
            self.doc_freqs = data.get('doc_freqs', {})
            self.doc_len = {k: int(v) for k, v in data.get('doc_len', {}).items()}
            self.avgdl = data.get('avgdl', 0)
            self.n_docs = data.get('n_docs', 0)
            
            logger.info(f"BM25 index loaded from {self.persist_path}: {self.n_docs} documents")
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            self.documents = {}
            self.doc_freqs = {}
            self.doc_len = {}
            self.avgdl = 0
            self.n_docs = 0


class HybridSearchResult:
    """混合检索结果"""
    
    @staticmethod
    def reciprocal_rank_fusion(
        vector_results: List[Tuple[Any, float]],
        bm25_results: List[Tuple[BM25Document, float]],
        alpha: float = 0.5,
        k: int = 60,
    ) -> List[Tuple[Any, float]]:
        """
        倒数排名融合 (RRF) 算法
        
        RRF score = sum(1 / (k + rank_i)) for each ranking list
        
        Args:
            vector_results: 向量检索结果 [(doc, score), ...]
            bm25_results: BM25 检索结果 [(doc, score), ...]
            alpha: 向量检索权重 (1-alpha 为 BM25 权重)
            k: RRF 常数，默认 60
        
        Returns:
            融合后的排序结果 [(doc, score), ...]
        """
        rrf_scores: Dict[str, Dict[str, Any]] = {}
        
        for rank, (doc, score) in enumerate(vector_results):
            doc_id = getattr(doc, 'id', getattr(doc, 'chunk_id', str(id(doc))))
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {'doc': doc, 'score': 0.0}
            rrf_scores[doc_id]['score'] += alpha / (k + rank + 1)
        
        for rank, (doc, score) in enumerate(bm25_results):
            doc_id = doc.id
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {'doc': doc, 'score': 0.0}
            rrf_scores[doc_id]['score'] += (1 - alpha) / (k + rank + 1)
        
        results = [
            (data['doc'], data['score'])
            for data in rrf_scores.values()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    @staticmethod
    def weighted_fusion(
        vector_results: List[Tuple[Any, float]],
        bm25_results: List[Tuple[BM25Document, float]],
        alpha: float = 0.5,
    ) -> List[Tuple[Any, float]]:
        """
        加权融合
        
        Args:
            vector_results: 向量检索结果 [(doc, score), ...]
            bm25_results: BM25 检索结果 [(doc, score), ...]
            alpha: 向量检索权重
        
        Returns:
            融合后的排序结果
        """
        def normalize_scores(results: List[Tuple]) -> List[Tuple]:
            if not results:
                return results
            scores = [s for _, s in results]
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s:
                return [(d, 1.0) for d, s in results]
            return [(d, (s - min_s) / (max_s - min_s)) for d, s in results]
        
        vector_norm = normalize_scores(vector_results)
        bm25_norm = normalize_scores(bm25_results)
        
        combined: Dict[str, Dict[str, Any]] = {}
        
        for doc, score in vector_norm:
            doc_id = getattr(doc, 'id', getattr(doc, 'chunk_id', str(id(doc))))
            if doc_id not in combined:
                combined[doc_id] = {'doc': doc, 'score': 0.0}
            combined[doc_id]['score'] += alpha * score
        
        for doc, score in bm25_norm:
            doc_id = doc.id
            if doc_id not in combined:
                combined[doc_id] = {'doc': doc, 'score': 0.0}
            combined[doc_id]['score'] += (1 - alpha) * score
        
        results = [
            (data['doc'], data['score'])
            for data in combined.values()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
