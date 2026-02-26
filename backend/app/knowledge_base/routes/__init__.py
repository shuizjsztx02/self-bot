from .auth import router as auth_router
from .knowledge_bases import router as kb_router
from .documents import router as documents_router
from .search import router as search_router
from .user_groups import router as user_groups_router
from .operation_logs import router as operation_logs_router
from .attribute_rules import router as attribute_rules_router

__all__ = [
    "auth_router",
    "kb_router",
    "documents_router",
    "search_router",
    "user_groups_router",
    "operation_logs_router",
    "attribute_rules_router",
]
