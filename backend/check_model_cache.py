import sys
sys.path.insert(0, '.')

print("=" * 60)
print("检查 BGE 模型本地缓存位置")
print("=" * 60)

import os
from pathlib import Path

print("\n1. HuggingFace 默认缓存位置:")
hf_cache = os.environ.get('HF_HOME', Path.home() / '.cache' / 'huggingface')
print(f"   HF_HOME: {hf_cache}")

hub_cache = os.environ.get('HUGGINGFACE_HUB_CACHE', Path(hf_cache) / 'hub')
print(f"   HUGGINGFACE_HUB_CACHE: {hub_cache}")

print("\n2. 检查模型缓存目录:")
hub_path = Path(hub_cache)
if hub_path.exists():
    print(f"   ✅ 缓存目录存在: {hub_path}")
    
    models = list(hub_path.glob("models--*"))
    if models:
        print(f"\n   已缓存的模型 ({len(models)} 个):")
        for model_dir in models:
            model_name = model_dir.name.replace("models--", "").replace("--", "/")
            
            size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
            size_mb = size / (1024 * 1024)
            
            print(f"   - {model_name}")
            print(f"     路径: {model_dir}")
            print(f"     大小: {size_mb:.2f} MB")
    else:
        print("   未找到已缓存的模型")
else:
    print(f"   ❌ 缓存目录不存在: {hub_path}")

print("\n3. 检查 sentence-transformers 缓存:")
st_cache = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
if st_cache.exists():
    print(f"   ✅ 缓存目录存在: {st_cache}")
    models = list(st_cache.glob("*"))
    if models:
        print(f"   已缓存的模型: {[m.name for m in models]}")
else:
    print(f"   缓存目录不存在: {st_cache}")

print("\n4. 检查 BGE 模型文件:")

bge_embedding_name = "models--BAAI--bge-base-zh-v1.5"
bge_reranker_name = "models--BAAI--bge-reranker-base"

for model_name in [bge_embedding_name, bge_reranker_name]:
    model_path = hub_path / model_name
    if model_path.exists():
        print(f"\n   ✅ {model_name.replace('models--', '').replace('--', '/')}")
        print(f"      路径: {model_path}")
        
        snapshots_path = model_path / "snapshots"
        if snapshots_path.exists():
            snapshots = list(snapshots_path.iterdir())
            if snapshots:
                latest = snapshots[0]
                print(f"      快照: {latest.name}")
                
                files = list(latest.glob("*"))
                print(f"      文件数: {len(files)}")
                
                total_size = sum(f.stat().st_size for f in latest.rglob('*') if f.is_file())
                print(f"      总大小: {total_size / (1024 * 1024):.2f} MB")
    else:
        print(f"\n   ❌ {model_name.replace('models--', '').replace('--', '/')} 未找到")

print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print(f"\n模型缓存根目录: {hub_path}")
print("\n如需更改缓存位置，可设置环境变量:")
print("  export HF_HOME=/path/to/cache")
print("  export HUGGINGFACE_HUB_CACHE=/path/to/cache/hub")
