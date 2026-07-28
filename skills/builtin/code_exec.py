# skills/builtin/code_exec.py
"""
代码执行 Skill
"""

import logging
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.code_exec")


class CodeExecutionSkill(BaseSkill):
    def __init__(self, hot_swap_manager=None, sandbox=None):
        self.hot_swap_manager = hot_swap_manager
        self.sandbox = sandbox
        super().__init__(SkillMetadata(
            id="code_execution",
            name="代码执行",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="执行代码片段",
            triggers={
                "keywords": ["运行代码", "执行代码", "code", "run", "python"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("code", "string", True, "要执行的代码"),
                SkillParameter("language", "string", False, "编程语言", "python"),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        code = params.get("code", "")
        language = params.get("language", "python")

        if not code:
            return {"success": False, "outputs": {}, "error": "缺少 code 参数"}

        try:
            if language.lower() == "python":
                result = await self._execute_python(code)
                return {"success": True, "outputs": {"result": result}}
            else:
                return {"success": False, "outputs": {}, "error": f"不支持的语言: {language}"}
        except Exception as e:
            logger.error(f"代码执行失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    async def _execute_python(self, code: str) -> str:
        import io
        import sys
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected = io.StringIO()
        sys.stdout = redirected
        sys.stderr = redirected
        try:
            exec_globals = {"__name__": "__main__"}
            exec(code, exec_globals)
            return redirected.getvalue() or "执行成功，无输出"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
