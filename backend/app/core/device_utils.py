"""
设备检测与选择模块

自动检测运行环境的 GPU 资源，选择最优设备进行模型推理
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def detect_cuda() -> Tuple[bool, str]:
    """
    检测 CUDA GPU 是否可用
    
    Returns:
        (is_available: bool, device_name: str)
    """
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            device_count = torch.cuda.device_count()
            memory_info = torch.cuda.get_device_properties(0)
            total_memory = memory_info.total_memory / (1024**3)
            
            logger.info(f"CUDA GPU detected: {device_name}")
            logger.info(f"  - Device count: {device_count}")
            logger.info(f"  - Total memory: {total_memory:.1f} GB")
            
            return True, "cuda:0"
        return False, ""
    except ImportError:
        logger.debug("PyTorch not installed, CUDA detection skipped")
        return False, ""
    except Exception as e:
        logger.warning(f"CUDA detection failed: {e}")
        return False, ""


def detect_mps() -> Tuple[bool, str]:
    """
    检测 Apple MPS (Metal Performance Shaders) 是否可用
    
    Returns:
        (is_available: bool, device_name: str)
    """
    try:
        import torch
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            logger.info("Apple MPS GPU detected")
            return True, "mps"
        return False, ""
    except ImportError:
        return False, ""
    except Exception as e:
        logger.debug(f"MPS detection failed: {e}")
        return False, ""


def get_optimal_device(force_cpu: bool = False) -> str:
    """
    获取最优设备
    
    优先级: CUDA > MPS > CPU
    
    Args:
        force_cpu: 是否强制使用 CPU
    
    Returns:
        设备字符串: "cuda:0", "mps", 或 "cpu"
    """
    if force_cpu:
        logger.info("Force CPU mode enabled")
        return "cpu"
    
    is_cuda, device = detect_cuda()
    if is_cuda:
        return device
    
    is_mps, device = detect_mps()
    if is_mps:
        return device
    
    logger.info("No GPU detected, using CPU")
    return "cpu"


def get_device_info() -> dict:
    """
    获取设备详细信息
    
    Returns:
        设备信息字典
    """
    info = {
        "device": "cpu",
        "cuda_available": False,
        "mps_available": False,
        "device_name": "CPU",
        "device_count": 0,
        "total_memory_gb": 0.0,
    }
    
    try:
        import torch
        
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["device"] = "cuda:0"
            info["device_name"] = torch.cuda.get_device_name(0)
            info["device_count"] = torch.cuda.device_count()
            props = torch.cuda.get_device_properties(0)
            info["total_memory_gb"] = round(props.total_memory / (1024**3), 1)
        
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            info["mps_available"] = True
            info["device"] = "mps"
            info["device_name"] = "Apple Silicon GPU"
    
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Failed to get device info: {e}")
    
    return info


def log_device_status():
    """打印当前设备状态"""
    info = get_device_info()
    
    logger.info("=" * 50)
    logger.info("Device Status")
    logger.info("=" * 50)
    logger.info(f"  Selected Device: {info['device']}")
    logger.info(f"  Device Name: {info['device_name']}")
    logger.info(f"  CUDA Available: {info['cuda_available']}")
    logger.info(f"  MPS Available: {info['mps_available']}")
    if info['device_count'] > 0:
        logger.info(f"  GPU Count: {info['device_count']}")
        logger.info(f"  GPU Memory: {info['total_memory_gb']} GB")
    logger.info("=" * 50)
