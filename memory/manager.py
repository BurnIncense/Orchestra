"""
四层记忆管理器 — 工作记忆 / 短期记忆 / 长期摘要 / 用户偏好
"""

import time
import logging

from memory.persistence import save_pickle, load_pickle

logger = logging.getLogger("orchestra.memory")


class MemoryManager:
    """四层记忆管理器"""

    def __init__(self, config: dict, memory_llm=None):
        self.config = config or {}
        self.max_working_turns = self.config.get("max_working_turns", 10)
        self.compress_threshold = self.config.get("compress_threshold", 20)
        self.persist_path = self.config.get("persist_path", "")
        self.auto_save_interval = self.config.get("auto_save_interval", 10)
        self.memory_llm = memory_llm

        self.working_memory: list[dict] = []
        self.short_term_memory: list[dict] = []
        self.long_term_summary: str = ""
        self.preferences: dict = {}
        self.turn_count: int = 0
        self.last_save_turn: int = 0

        if self.persist_path:
            self.load()

    def add_turn(self, role: str, content: str) -> None:
        """添加一轮对话到工作记忆"""
        turn = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        self.working_memory.append(turn)
        self.turn_count += 1

        while len(self.working_memory) > self.max_working_turns:
            evicted = self.working_memory.pop(0)
            self.short_term_memory.append(evicted)

        if self.auto_save_interval > 0 and (self.turn_count - self.last_save_turn) >= self.auto_save_interval:
            self.save()

    def get_context(self) -> str:
        """返回完整上下文字符串"""
        parts = []

        if self.long_term_summary:
            parts.append(f"[长期记忆摘要]\n{self.long_term_summary}")

        if self.short_term_memory:
            stm_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in self.short_term_memory
            )
            parts.append(f"[短期记忆]\n{stm_text}")

        if self.working_memory:
            wm_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in self.working_memory
            )
            parts.append(f"[工作记忆]\n{wm_text}")

        return "\n\n".join(parts)

    def get_recent_messages(self, n: int = 6) -> list[dict]:
        """返回最近 n 轮消息"""
        all_messages = self.short_term_memory + self.working_memory
        recent = all_messages[-n:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def should_compress(self) -> bool:
        """判断是否需要压缩短期记忆"""
        return len(self.short_term_memory) >= self.compress_threshold

    async def compress(self) -> None:
        """调用 memory_llm 把短期记忆压缩进长期摘要"""
        if not self.memory_llm or not self.short_term_memory:
            return

        try:
            from memory.compressor import DialogueCompressor
            compressor = DialogueCompressor(self.memory_llm)
            new_summary = await compressor.compress(
                self.short_term_memory,
                existing_summary=self.long_term_summary,
            )
            self.long_term_summary = new_summary
            self.short_term_memory.clear()
            logger.info(f"短期记忆已压缩，当前长期摘要长度: {len(new_summary)}")
        except Exception as e:
            logger.error(f"记忆压缩失败: {e}")

    def save(self) -> None:
        """用 pickle 保存整个对象到 persist_path"""
        if not self.persist_path:
            return
        data = {
            "working_memory": self.working_memory,
            "short_term_memory": self.short_term_memory,
            "long_term_summary": self.long_term_summary,
            "preferences": self.preferences,
            "turn_count": self.turn_count,
            "last_save_turn": self.last_save_turn,
        }
        save_pickle(self.persist_path, data)
        self.last_save_turn = self.turn_count

    def load(self) -> None:
        """从 persist_path 加载"""
        if not self.persist_path:
            return
        data = load_pickle(self.persist_path, None)
        if data is None:
            return
        self.working_memory = data.get("working_memory", [])
        self.short_term_memory = data.get("short_term_memory", [])
        self.long_term_summary = data.get("long_term_summary", "")
        self.preferences = data.get("preferences", {})
        self.turn_count = data.get("turn_count", 0)
        self.last_save_turn = data.get("last_save_turn", 0)
