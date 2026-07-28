"""
会话管理器 — 多用户状态完全隔离

每个用户连接创建独立的 Session：
- 独立的 MemoryManager（对话历史）
- 独立的 SkillLearner（偏好）
- 独立的 RuntimeCallGuard（调用栈）
- 独立的 Trace ID
- 共享的 SkillRegistry / HotSwapManager / MCP Client
"""

import uuid
import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger("orchestra.session")


@dataclass
class SessionConfig:
    max_idle_seconds: float = 3600.0
    max_turns: int = 100
    persist: bool = True


class Session:
    """用户会话（状态完全隔离）"""

    def __init__(self, session_id: str, user_id: str,
                 memory_llm, config: SessionConfig = None):
        self.session_id = session_id
        self.user_id = user_id
        self.config = config or SessionConfig()

        # 独立的记忆
        from memory.manager import MemoryManager
        self.memory = MemoryManager(
            config={
                "max_working_turns": 10,
                "persist_path": f"./data/memory/sessions/{user_id}/memory.pkl",
            },
            memory_llm=memory_llm,
        )

        # 独立的学习器（Per-User 偏好）
        from skills.learner import SkillLearner
        self.learner = SkillLearner(
            memory_llm=memory_llm,
            persist_path=f"./data/memory/sessions/{user_id}/preferences.json",
        )

        # 独立的调用守卫
        from core.dependency_graph import RuntimeCallGuard
        self.call_guard = RuntimeCallGuard()

        # Trace
        self.current_trace_id: str = ""

        # 元数据
        self.created_at = time.time()
        self.last_active = time.time()
        self.turn_count = 0

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > self.config.max_idle_seconds

    def get_context(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "memory": self.memory,
            "learner": self.learner,
            "call_guard": self.call_guard,
            "trace_id": self.current_trace_id,
        }

    def save(self):
        if self.config.persist:
            self.memory.save()
            self.learner._save()

    def cleanup(self):
        self.save()
        logger.info(f"🧹 会话清理: {self.session_id} (用户: {self.user_id})")


class SessionManager:
    """会话管理器"""

    MAX_SESSIONS = 50

    def __init__(self, memory_llm, cleanup_interval: float = 60.0):
        self.memory_llm = memory_llm
        self.cleanup_interval = cleanup_interval
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, str] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def get_or_create(self, user_id: str) -> Session:
        async with self._lock:
            if user_id in self._user_sessions:
                session_id = self._user_sessions[user_id]
                session = self._sessions.get(session_id)
                if session and not session.is_expired():
                    session.touch()
                    return session

            if len(self._sessions) >= self.MAX_SESSIONS:
                await self._evict_oldest()

            session_id = f"sess_{uuid.uuid4().hex[:12]}"
            session = Session(
                session_id=session_id,
                user_id=user_id,
                memory_llm=self.memory_llm,
            )
            self._sessions[session_id] = session
            self._user_sessions[user_id] = session_id
            logger.info(f"📝 新会话: {session_id} (用户: {user_id})")
            return session

    async def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    async def destroy(self, session_id: str):
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.save()
                self._user_sessions.pop(session.user_id, None)

    async def _evict_oldest(self):
        if not self._sessions:
            return
        oldest_id = min(self._sessions, key=lambda k: self._sessions[k].last_active)
        await self.destroy(oldest_id)

    async def start_cleanup_loop(self):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(self.cleanup_interval)
            expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
            for sid in expired:
                await self.destroy(sid)

    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
        for session in self._sessions.values():
            session.save()
        self._sessions.clear()
        self._user_sessions.clear()

    @property
    def active_count(self) -> int:
        return len(self._sessions)
