"""
图可视化模块

提供 LangGraph 图的可视化功能
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_graph_mermaid(graph) -> str:
    """
    获取图的 Mermaid 表示
    
    Args:
        graph: 编译后的图
        
    Returns:
        Mermaid 格式的图描述
    """
    try:
        return graph.get_graph().draw_mermaid()
    except Exception as e:
        logger.warning(f"[GraphViz] Could not generate Mermaid: {e}")
        return _generate_fallback_mermaid()


def _generate_fallback_mermaid() -> str:
    """生成后备的 Mermaid 图"""
    return """
graph TD
    A[START] --> B[classify_intent]
    B --> C{route_by_intent}
    C -->|rag| D[rag_retrieve]
    C -->|search| E[web_search]
    C -->|parallel| F[parallel_search]
    C -->|direct| G[generate_response]
    D --> G
    E --> G
    F --> G
    G --> H[finalize]
    H --> I[END]
"""


def get_graph_ascii(graph) -> str:
    """
    获取图的 ASCII 表示
    
    Args:
        graph: 编译后的图
        
    Returns:
        ASCII 格式的图描述
    """
    return """
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Supervisor Graph                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐                                                        │
│  │ classify_intent │ ──── 路由决策 ────┐                                     │
│  └─────────────────┘                   │                                     │
│                                        │                                     │
│          ┌─────────────────────────────┼─────────────────────────────┐      │
│          │                             │                             │      │
│          ▼                             ▼                             ▼      │
│  ┌─────────────┐              ┌─────────────┐              ┌───────────┐   │
│  │ rag_retrieve│              │ web_search  │              │  direct   │   │
│  └──────┬──────┘              └──────┬──────┘              └─────┬─────┘   │
│         │                            │                           │         │
│         │      ┌─────────────┐       │                           │         │
│         └─────►│ parallel_   │◄──────┘                           │         │
│                │ search      │                                    │         │
│                └──────┬──────┘                                    │         │
│                       │                                           │         │
│                       ▼                                           │         │
│              ┌─────────────────┐◄──────────────────────────────────┘         │
│              │ generate_response│                                            │
│              └────────┬────────┘                                            │
│                       │                                                      │
│                       ▼                                                      │
│              ┌─────────────────┐                                            │
│              │    finalize     │                                            │
│              └────────┬────────┘                                            │
│                       │                                                      │
│                       ▼                                                      │
│                      END                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
"""


def save_graph_image(graph, output_path: str, format: str = "png") -> bool:
    """
    保存图为图片
    
    Args:
        graph: 编译后的图
        output_path: 输出路径
        format: 图片格式 (png, svg, pdf)
        
    Returns:
        是否成功
    """
    try:
        from langgraph.graph import StateGraph
        
        image_data = graph.get_graph().draw_mermaid_png()
        
        with open(output_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"[GraphViz] Saved graph image to {output_path}")
        return True
        
    except ImportError:
        logger.warning("[GraphViz] mermaid-cli not installed, cannot generate image")
        return False
    except Exception as e:
        logger.error(f"[GraphViz] Error saving graph image: {e}")
        return False


def print_graph_structure(graph):
    """
    打印图结构
    
    Args:
        graph: 编译后的图
    """
    print(get_graph_ascii(graph))
    
    try:
        nodes = graph.nodes
        edges = graph.edges
        
        print("\n节点列表:")
        for node_name in nodes:
            print(f"  - {node_name}")
        
        print("\n边列表:")
        for edge in edges:
            print(f"  - {edge}")
            
    except Exception as e:
        logger.debug(f"[GraphViz] Could not get graph details: {e}")


class GraphVisualizer:
    """
    图可视化器
    
    提供图可视化的便捷接口
    """
    
    def __init__(self, graph):
        """
        初始化可视化器
        
        Args:
            graph: 编译后的图
        """
        self._graph = graph
    
    def get_mermaid(self) -> str:
        """获取 Mermaid 格式"""
        return get_graph_mermaid(self._graph)
    
    def get_ascii(self) -> str:
        """获取 ASCII 格式"""
        return get_graph_ascii(self._graph)
    
    def save_image(self, output_path: str, format: str = "png") -> bool:
        """保存为图片"""
        return save_graph_image(self._graph, output_path, format)
    
    def print_structure(self):
        """打印结构"""
        print_graph_structure(self._graph)
    
    def to_json(self) -> Dict[str, Any]:
        """
        转换为 JSON 格式
        
        Returns:
            图结构的 JSON 表示
        """
        try:
            nodes = list(self._graph.nodes.keys()) if hasattr(self._graph, 'nodes') else []
            edges = []
            
            if hasattr(self._graph, 'edges'):
                for edge in self._graph.edges:
                    if hasattr(edge, 'source') and hasattr(edge, 'target'):
                        edges.append({
                            "source": edge.source,
                            "target": edge.target,
                            "conditional": getattr(edge, 'conditional', False),
                        })
                    else:
                        edges.append(str(edge))
            
            return {
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
            
        except Exception as e:
            logger.debug(f"[GraphViz] Could not convert to JSON: {e}")
            return {
                "nodes": [],
                "edges": [],
                "error": str(e),
            }
