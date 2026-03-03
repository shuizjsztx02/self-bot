"""
全量切换到 LangGraph 架构

运行此脚本启用 LangGraph 架构
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def enable_langgraph():
    """启用 LangGraph 架构"""
    backend_dir = Path(__file__).parent.parent
    env_file = backend_dir / ".env"
    
    print("=" * 60)
    print("全量切换到 LangGraph 架构")
    print("=" * 60)
    
    env_content = ""
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            env_content = f.read()
    
    lines = env_content.split("\n")
    updated_lines = []
    found = False
    
    for line in lines:
        if line.startswith("USE_LANGGRAPH="):
            updated_lines.append("USE_LANGGRAPH=true")
            found = True
        else:
            updated_lines.append(line)
    
    if not found:
        if updated_lines and updated_lines[-1]:
            updated_lines.append("")
        updated_lines.append("# LangGraph 架构开关")
        updated_lines.append("USE_LANGGRAPH=true")
    
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines))
    
    print("\n✅ 已启用 LangGraph 架构")
    print(f"   配置文件: {env_file}")
    print("\n重启服务器后生效:")
    print("   python run.py --reload")
    print("=" * 60)


def disable_langgraph():
    """禁用 LangGraph 架构（回滚）"""
    backend_dir = Path(__file__).parent.parent
    env_file = backend_dir / ".env"
    
    print("=" * 60)
    print("回滚到旧架构")
    print("=" * 60)
    
    if not env_file.exists():
        print("\n⚠️ .env 文件不存在")
        return
    
    with open(env_file, "r", encoding="utf-8") as f:
        env_content = f.read()
    
    lines = env_content.split("\n")
    updated_lines = []
    
    for line in lines:
        if line.startswith("USE_LANGGRAPH="):
            updated_lines.append("USE_LANGGRAPH=false")
        else:
            updated_lines.append(line)
    
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines))
    
    print("\n✅ 已回滚到旧架构")
    print(f"   配置文件: {env_file}")
    print("\n重启服务器后生效:")
    print("   python run.py --reload")
    print("=" * 60)


def check_status():
    """检查当前状态"""
    from app.langchain.graph.feature_flags import GraphFeatureFlags
    
    print("=" * 60)
    print("LangGraph 架构状态")
    print("=" * 60)
    
    status = GraphFeatureFlags.get_status()
    
    print(f"\n  USE_LANGGRAPH: {status['use_langgraph']}")
    print(f"  PARALLEL_ENABLED: {status['parallel_enabled']}")
    print(f"  TRAFFIC_RATIO: {status['traffic_ratio']:.0%}")
    
    if status['use_langgraph']:
        print("\n  ✅ 当前使用 LangGraph 架构")
    else:
        print("\n  ⚠️ 当前使用旧架构")
    
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LangGraph 架构切换工具")
    parser.add_argument(
        "action",
        choices=["enable", "disable", "status"],
        help="操作: enable=启用, disable=禁用, status=查看状态"
    )
    
    args = parser.parse_args()
    
    if args.action == "enable":
        enable_langgraph()
    elif args.action == "disable":
        disable_langgraph()
    elif args.action == "status":
        check_status()
