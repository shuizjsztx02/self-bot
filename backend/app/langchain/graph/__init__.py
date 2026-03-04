"""
LangGraph 模块

包含状态定义、节点、图构建等组件
"""
from .state import (
    SupervisorState, 
    StateAdapter, 
    create_initial_state, 
    QueryIntent,
    RouteDecision,
    SourceReference,
    ToolCallRecord,
)
from .feature_flags import GraphFeatureFlags, with_langgraph_fallback
from .adapters import (
    IntentAdapter,
    IntentResult,
    RagAdapter,
    RagResult,
    SearchAdapter,
    SearchResult,
    ParallelResultAdapter,
    MainAgentAdapter,
    AgentResponse,
    ToolCallAdapter,
)
from .supervisor_graph import (
    build_base_graph,
    build_supervisor_graph,
    build_simple_graph,
    SupervisorGraphRunner,
)
from .tracer import (
    GraphTracer,
    GraphTrace,
    NodeExecution,
    get_graph_tracer,
    traced_node,
)
from .visualizer import (
    GraphVisualizer,
    get_graph_mermaid,
    get_graph_ascii,
)
from .switch_manager import (
    SwitchManager,
    get_switch_manager,
    with_architecture_switch,
)
from .service import (
    LangGraphService,
    should_use_langgraph,
    get_agent,
)
from .metrics import (
    MetricsCollector,
    get_metrics_collector,
    with_metrics,
    ABTestAnalyzer,
    get_ab_test_analyzer,
)

__all__ = [
    "SupervisorState",
    "StateAdapter",
    "create_initial_state",
    "QueryIntent",
    "RouteDecision",
    "SourceReference",
    "ToolCallRecord",
    "GraphFeatureFlags",
    "with_langgraph_fallback",
    "IntentAdapter",
    "IntentResult",
    "RagAdapter",
    "RagResult",
    "SearchAdapter",
    "SearchResult",
    "ParallelResultAdapter",
    "MainAgentAdapter",
    "AgentResponse",
    "ToolCallAdapter",
    "build_base_graph",
    "build_supervisor_graph",
    "build_simple_graph",
    "SupervisorGraphRunner",
    "GraphTracer",
    "GraphTrace",
    "NodeExecution",
    "get_graph_tracer",
    "traced_node",
    "GraphVisualizer",
    "get_graph_mermaid",
    "get_graph_ascii",
    "SwitchManager",
    "get_switch_manager",
    "with_architecture_switch",
    "LangGraphService",
    "should_use_langgraph",
    "get_agent",
    "MetricsCollector",
    "get_metrics_collector",
    "with_metrics",
    "ABTestAnalyzer",
    "get_ab_test_analyzer",
]
