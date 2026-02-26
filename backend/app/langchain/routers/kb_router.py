from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.models import KnowledgeBase
from app.knowledge_base.services.embedding import EmbeddingService
from sqlalchemy import select


class KBRouter:
    """
    知识库路由器
    
    决定应该检索哪些知识库
    """
    
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService = None,
    ):
        self.db = db
        self._embedding_service = embedding_service
        self._kb_embeddings = {}
    
    @property
    def embedding_service(self):
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service
    
    async def route(
        self,
        query: str,
        user_id: str,
        permission_service,
        kb_hints: List[str] = None,
    ) -> List[str]:
        """
        路由决策
        
        Args:
            query: 用户查询
            user_id: 用户ID
            permission_service: 权限服务
            kb_hints: 意图分类器给出的知识库提示
        
        Returns:
            应该检索的知识库ID列表
        """
        accessible_kbs = await permission_service.get_accessible_kbs(user_id)
        
        if not accessible_kbs:
            return []
        
        if kb_hints:
            hinted_kbs = []
            result = await self.db.execute(
                select(KnowledgeBase).where(KnowledgeBase.name.in_(kb_hints))
            )
            for kb in result.scalars().all():
                if kb.id in accessible_kbs:
                    hinted_kbs.append(kb.id)
            
            if hinted_kbs:
                return hinted_kbs
        
        if len(accessible_kbs) == 1:
            return accessible_kbs
        
        return await self._semantic_route(query, accessible_kbs)
    
    async def _semantic_route(
        self,
        query: str,
        kb_ids: List[str],
    ) -> List[str]:
        """
        语义路由：根据查询与知识库的语义相似度选择
        """
        if not kb_ids:
            return []
        
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
        )
        kbs = list(result.scalars().all())
        
        if not kbs:
            return []
        
        query_embedding = await self.embedding_service.embed_text(query)
        
        kb_scores = []
        for kb in kbs:
            kb_text = f"{kb.name} {kb.description or ''}"
            
            if kb.id in self._kb_embeddings:
                kb_embedding = self._kb_embeddings[kb.id]
            else:
                kb_embedding = await self.embedding_service.embed_text(kb_text)
                self._kb_embeddings[kb.id] = kb_embedding
            
            similarity = self._cosine_similarity(query_embedding, kb_embedding)
            kb_scores.append((kb.id, similarity))
        
        kb_scores.sort(key=lambda x: x[1], reverse=True)
        
        top_kbs = [kb_id for kb_id, score in kb_scores[:3] if score > 0.3]
        
        return top_kbs if top_kbs else [kb_scores[0][0]]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        import math
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def clear_cache(self):
        """清除知识库嵌入缓存"""
        self._kb_embeddings.clear()
