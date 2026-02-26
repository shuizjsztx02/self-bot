import sys
sys.path.insert(0, '.')

print("检查依赖版本...")

try:
    import sklearn
    print(f"sklearn version: {sklearn.__version__}")
except Exception as e:
    print(f"sklearn error: {e}")

try:
    import sentence_transformers
    print(f"sentence_transformers version: {sentence_transformers.__version__}")
except Exception as e:
    print(f"sentence_transformers error: {e}")

try:
    import torch
    print(f"torch version: {torch.__version__}")
except Exception as e:
    print(f"torch error: {e}")

try:
    import transformers
    print(f"transformers version: {transformers.__version__}")
except Exception as e:
    print(f"transformers error: {e}")
