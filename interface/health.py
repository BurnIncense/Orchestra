"""健康检查端点"""

import time

_start_time = time.time()

try:
    from fastapi import APIRouter
    router = APIRouter()
except ImportError:
    router = None


if router is not None:
    @router.get("/health")
    async def health():
        return {"status": "alive", "uptime": time.time() - _start_time}


    @router.get("/ready")
    async def ready(agent=None):
        try:
            gpu_ok = __import__("torch").cuda.is_available()
        except ImportError:
            gpu_ok = False
        checks = {
            "thinker": agent.thinker.is_available() if agent else False,
            "memory_llm": agent.memory_llm.is_available() if agent else False,
            "gpu": gpu_ok,
            "skills": agent.registry.count > 0 if agent else False,
        }
        return {"status": "ready" if all(checks.values()) else "not_ready", "checks": checks}


    @router.get("/status")
    async def full_status(agent=None):
        return {
            "version": "2.2.0",
            "uptime": time.time() - _start_time,
            "gpu": agent.hot_swap.status() if agent else {},
            "sessions": agent.session_manager.active_count if agent else 0,
            "skills": agent.registry.count if agent else 0,
        }
