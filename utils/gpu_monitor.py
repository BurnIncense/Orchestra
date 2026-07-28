def get_gpu_info() -> dict:
    try:
        import torch
    except ImportError:
        return {}

    if not torch.cuda.is_available():
        return {}

    info = {}
    device_count = torch.cuda.device_count()
    info["device_count"] = device_count

    for i in range(device_count):
        props = torch.cuda.get_device_properties(i)
        free, total = torch.cuda.mem_get_info(i)
        allocated = torch.cuda.memory_allocated(i)
        reserved = torch.cuda.memory_reserved(i)
        info[f"gpu_{i}"] = {
            "name": props.name,
            "total_gb": round(total / 1024 ** 3, 2),
            "free_gb": round(free / 1024 ** 3, 2),
            "used_gb": round((total - free) / 1024 ** 3, 2),
            "allocated_gb": round(allocated / 1024 ** 3, 2),
            "reserved_gb": round(reserved / 1024 ** 3, 2),
        }

    return info
