import os
from pathlib import Path


def get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def ensure_dir(path: Path) -> Path:
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def safe_join(base: str, *parts) -> str:
    base_path = os.path.abspath(base)
    result = os.path.abspath(os.path.join(base_path, *parts))
    if not result.startswith(base_path + os.sep) and result != base_path:
        raise ValueError(f"路径穿越被拒绝: {result}")
    return result
