"""
执行引擎 — 统一 Skill 执行入口，带超时控制
"""

import asyncio
import logging

logger = logging.getLogger("orchestra.executor")


class SkillExecutor:
    def __init__(self, router, dispatcher):
        self.router = router
        self.dispatcher = dispatcher

    async def execute(self, skill_id: str, params: dict, context: dict = None,
                      timeout: float = 300.0) -> dict:
        if not skill_id:
            return {"success": False, "error": "skill_id 为空"}

        if params is None:
            params = {}

        try:
            result = await asyncio.wait_for(
                self._execute_internal(skill_id, params, context),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Skill 执行超时 ({timeout}s): {skill_id}")
            return {"success": False, "error": f"执行超时 ({timeout}s)"}
        except Exception as e:
            logger.exception(f"Skill 执行异常: {skill_id}")
            return {"success": False, "error": str(e)}

    async def _execute_internal(self, skill_id: str, params: dict, context: dict = None) -> dict:
        if self.router is not None:
            try:
                return await self.router.call_skill(skill_id, params, context)
            except Exception as e:
                logger.warning(f"Router 调用失败，尝试 Dispatcher: {e}")

        if self.dispatcher is not None:
            skill = None
            try:
                if self.router is not None and hasattr(self.router, "registry"):
                    skill = self.router.registry.get(skill_id)
            except Exception:
                pass

            if skill is not None:
                return await self.dispatcher.execute(skill, params, context)

        return {"success": False, "error": f"无法执行 Skill: {skill_id}"}
