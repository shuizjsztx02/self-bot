"""
Supervisor 状态定义

定义 LangGraph 图中使用的状态结构和适配器
"""
from typing import TypedDict, Annotated, Optional, List, Any, Dict, Union
from langgraph.graph.message import add_messages
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    """查询意图枚举"""
    KB_QUERY = "kb_query"
    SEARCH_TASK = "search_task"
    DOCUMENT_TASK = "document_task"
    DATA_ANALYSIS = "data_analysis"
    CODE_TASK = "code_task"
    TOOL_TASK = "tool_task"
    GENERAL_CHAT = "general_chat"
    AMBIGUOUS = "ambiguous"


class RouteDecision(str, Enum):
    """路由决策枚举"""
    RAG_FIRST = "rag_first"
    RESEARCH_FIRST = "research_first"
    TOOL_FIRST = "tool_first"
    DIRECT = "direct"
    PARALLEL = "parallel"


@dataclass
class SourceReference:
    """来源引用"""
    id: str
    title: str
    source_type: str  # "kb", "web", "file"
    score: float = 0.0
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    success: bool = True
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class SupervisorState(TypedDict, total=False):
    """
    Supervisor 状态定义
    
    设计原则:
    1. 字段与现有 Agent 输入输出对齐
    2. 支持增量更新
    3. 可序列化 (用于调试和持久化)
    
    字段分组:
    
    === 基础字段 ===
    messages: 消息列表，使用 add_messages 注解自动追加
    query: 用户原始查询
    rewritten_query: 重写后的查询
    
    === 意图分类字段 ===
    intent: 分类后的意图
    confidence: 意图分类置信度
    kb_hints: 知识库提示列表
    secondary_intents: 备选意图列表
    reasoning: 分类理由
    
    === RAG 检索字段 ===
    rag_context: RAG 检索上下文
    rag_sources: RAG 检索来源
    rag_documents: RAG 检索文档列表
    rag_entities: 提取的实体列表
    rag_query_variations: 查询变体
    
    === 搜索字段 ===
    search_context: 互联网搜索上下文
    search_sources: 搜索来源列表
    search_iterations: 搜索迭代次数
    
    === 响应字段 ===
    final_response: 最终响应
    tool_calls: 工具调用记录
    
    === 路由字段 ===
    route: 路由决策
    route_confidence: 路由置信度
    parallel_results: 并行执行结果
    
    === 会话字段 ===
    user_id: 用户 ID
    conversation_id: 会话 ID
    db_session: 数据库会话 (不序列化)
    
    === 错误处理字段 ===
    error: 错误信息
    error_node: 错误发生节点
    error_traceback: 错误堆栈
    
    === 元数据字段 ===
    start_time: 开始时间
    end_time: 结束时间
    total_tokens: 总 token 数
    node_executions: 节点执行记录
    """
    
    messages: Annotated[list, add_messages]
    
    query: str
    rewritten_query: Optional[str]
    
    intent: Optional[str]
    confidence: Optional[float]
    kb_hints: Optional[List[str]]
    secondary_intents: Optional[List[Dict[str, Any]]]
    reasoning: Optional[str]
    
    rag_context: Optional[str]
    rag_sources: Optional[List[Dict[str, Any]]]
    rag_documents: Optional[List[Dict[str, Any]]]
    rag_entities: Optional[List[str]]
    rag_query_variations: Optional[List[str]]
    
    search_context: Optional[str]
    search_sources: Optional[List[Dict[str, Any]]]
    search_iterations: Optional[int]
    
    final_response: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    
    route: Optional[str]
    route_confidence: Optional[float]
    parallel_results: Optional[List[Dict[str, Any]]]
    
    user_id: Optional[str]
    conversation_id: Optional[str]
    db_session: Optional[Any]
    
    error: Optional[str]
    error_node: Optional[str]
    error_traceback: Optional[str]
    
    start_time: Optional[str]
    end_time: Optional[str]
    total_tokens: Optional[int]
    node_executions: Optional[List[Dict[str, Any]]]


class StateAdapter:
    """
    状态适配器
    
    负责在不同数据结构之间转换:
    - dict <-> SupervisorState
    - Agent Result <-> SupervisorState
    """
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> SupervisorState:
        """
        从字典创建状态
        
        Args:
            data: 输入字典
            
        Returns:
            SupervisorState 实例
        """
        return SupervisorState(
            messages=data.get("messages", []),
            query=data.get("query", ""),
            rewritten_query=data.get("rewritten_query"),
            intent=data.get("intent"),
            confidence=data.get("confidence"),
            kb_hints=data.get("kb_hints"),
            secondary_intents=data.get("secondary_intents"),
            reasoning=data.get("reasoning"),
            rag_context=data.get("rag_context"),
            rag_sources=data.get("rag_sources"),
            rag_documents=data.get("rag_documents"),
            rag_entities=data.get("rag_entities"),
            rag_query_variations=data.get("rag_query_variations"),
            search_context=data.get("search_context"),
            search_sources=data.get("search_sources"),
            search_iterations=data.get("search_iterations"),
            final_response=data.get("final_response"),
            tool_calls=data.get("tool_calls"),
            route=data.get("route"),
            route_confidence=data.get("route_confidence"),
            parallel_results=data.get("parallel_results"),
            user_id=data.get("user_id"),
            conversation_id=data.get("conversation_id"),
            db_session=data.get("db_session"),
            error=data.get("error"),
            error_node=data.get("error_node"),
            error_traceback=data.get("error_traceback"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            total_tokens=data.get("total_tokens"),
            node_executions=data.get("node_executions"),
        )
    
    @staticmethod
    def to_dict(state: SupervisorState) -> Dict[str, Any]:
        """
        将状态转换为字典
        
        Args:
            state: SupervisorState 实例
            
        Returns:
            字典表示
        """
        result = dict(state)
        if "db_session" in result:
            del result["db_session"]
        return result
    
    @staticmethod
    def from_supervisor_agent(agent: Any) -> SupervisorState:
        """
        从现有 SupervisorAgent 创建状态
        
        Args:
            agent: SupervisorAgent 实例
            
        Returns:
            SupervisorState 实例
        """
        return SupervisorState(
            messages=[],
            query="",
            user_id=getattr(agent, 'user_id', None),
            conversation_id=getattr(agent, 'conversation_id', None),
            db_session=getattr(agent, 'db_session', None),
        )
    
    @staticmethod
    def to_agent_input(state: SupervisorState) -> Dict[str, Any]:
        """
        转换为 Agent 输入格式
        
        Args:
            state: SupervisorState 实例
            
        Returns:
            Agent 输入字典
        """
        return {
            "message": state.get("query", ""),
            "db": state.get("db_session"),
            "conversation_id": state.get("conversation_id"),
        }
    
    @staticmethod
    def merge(state: SupervisorState, updates: Dict[str, Any]) -> SupervisorState:
        """
        合并状态更新
        
        Args:
            state: 原始状态
            updates: 更新内容
            
        Returns:
            合并后的状态
        """
        result = dict(state)
        result.update(updates)
        return SupervisorState(**result)
    
    @staticmethod
    def serialize(state: SupervisorState) -> Dict[str, Any]:
        """
        序列化状态 (用于日志/持久化)
        
        移除不可序列化的字段
        
        Args:
            state: SupervisorState 实例
            
        Returns:
            可序列化的字典
        """
        result = StateAdapter.to_dict(state)
        
        if "messages" in result:
            result["messages"] = [
                {"role": m.get("role"), "content": m.get("content", "")[:100] + "..."}
                if isinstance(m, dict) and len(m.get("content", "")) > 100
                else m
                for m in result["messages"]
            ]
        
        return result
    
    @staticmethod
    def record_node_execution(
        state: SupervisorState,
        node_name: str,
        success: bool = True,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> SupervisorState:
        """
        记录节点执行
        
        Args:
            state: 当前状态
            node_name: 节点名称
            success: 是否成功
            duration_ms: 执行时长 (毫秒)
            error: 错误信息
            
        Returns:
            更新后的状态
        """
        executions = state.get("node_executions", [])
        executions.append({
            "node": node_name,
            "success": success,
            "duration_ms": duration_ms,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
        
        return StateAdapter.merge(state, {"node_executions": executions})


def create_initial_state(
    query: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    db_session: Optional[Any] = None,
) -> SupervisorState:
    """
    创建初始状态
    
    Args:
        query: 用户查询
        user_id: 用户 ID
        conversation_id: 会话 ID
        db_session: 数据库会话
        
    Returns:
        初始 SupervisorState
    """
    return SupervisorState(
        messages=[],
        query=query,
        rewritten_query=None,
        user_id=user_id,
        conversation_id=conversation_id,
        db_session=db_session,
        intent=None,
        confidence=None,
        kb_hints=None,
        secondary_intents=None,
        reasoning=None,
        rag_context=None,
        rag_sources=None,
        rag_documents=None,
        rag_entities=None,
        rag_query_variations=None,
        search_context=None,
        search_sources=None,
        search_iterations=None,
        final_response=None,
        tool_calls=None,
        route=None,
        route_confidence=None,
        parallel_results=None,
        error=None,
        error_node=None,
        error_traceback=None,
        start_time=datetime.now().isoformat(),
        end_time=None,
        total_tokens=0,
        node_executions=[],
    )
