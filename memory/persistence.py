"""
持久化工具 — 原子写、防抖、pickle、JSON
"""

import os
import time
import json
import pickle
import tempfile
from pathlib import Path


def atomic_write(path: str, data: bytes, mode: str = "wb") -> None:
    """原子写入：先写 .tmp 文件，再 rename 到目标路径"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    with open(tmp_path, mode) as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, target)


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    """原子写入文本"""
    atomic_write(path, text.encode(encoding))


_debounce_state = {}


def debounced_save(func, path: str, data, debounce_seconds: float = 2.0) -> None:
    """简单防抖保存（基于时间戳对比）"""
    now = time.time()
    last = _debounce_state.get(path, 0.0)
    if now - last < debounce_seconds:
        return
    _debounce_state[path] = now
    func(path, data)


def save_pickle(path: str, obj) -> None:
    """保存 pickle"""
    atomic_write(path, pickle.dumps(obj))


def load_pickle(path: str, default=None):
    """加载 pickle，不存在返回 default"""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return default


def save_json(path: str, data) -> None:
    """保存 JSON"""
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_json(path: str, default=None):
    """加载 JSON，不存在返回 default"""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default
