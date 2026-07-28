"""
任务规划器 — 将复杂用户需求拆解为多步执行计划
"""

import json
import logging
import re

logger = logging.getLogger("orchestra.planner")


class TaskPlanner:
    def __init__(self, llm_client):
        self.llm = llm_client

    def create_plan(self, user_input: str, memory_context: str = "") -> dict:
        if not user_input or not user_input.strip():
            return {"steps": []}

        llm_available = self._check_llm_available()

        if llm_available:
            try:
                return self._plan_with_llm(user_input, memory_context)
            except Exception as e:
                logger.warning(f"LLM 任务规划失败，降级到单步计划: {e}")

        return self._fallback_plan(user_input)

    def _check_llm_available(self) -> bool:
        try:
            if hasattr(self.llm, "is_available"):
                return self.llm.is_available()
        except Exception:
            pass
        return False

    def _plan_with_llm(self, user_input: str, memory_context: str) -> dict:
        skill_hints = """
可用 Skill ID 参考：
- image_generation: 图片生成
- image_understanding: 图片理解
- video_generation: 视频生成
- multishot_video: 多镜头视频
- code_execution: 代码执行
- web_search: 网页搜索
- data_analysis: 数据分析
- file_operations: 文件操作
"""

        prompt = f"""你是一个任务规划专家。请将用户的复杂任务拆解为多个执行步骤。

{skill_hints}

用户任务：{user_input}
历史上下文：{memory_context[:1000] if memory_context else "无"}

请以 JSON 格式返回执行计划，格式如下：
{{
  "steps": [
    {{
      "skill": "skill_id",
      "input": {{"param_name": "value"}},
      "description": "该步骤的简短描述"
    }}
  ]
}}

要求：
- 每步必须指定一个 skill ID
- input 是该 skill 需要的参数字典
- description 用一句话描述该步骤做什么
- 如果任务很简单，可以只有一步

只返回 JSON，不要其他内容。"""

        result = self.llm.chat(
            prompt=prompt,
            system="你是一个精确的任务规划器。",
            max_tokens=1024,
            temperature=0.3,
        )

        content = result.get("content", "").strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    parsed = {}
            else:
                parsed = {}

        steps = parsed.get("steps", [])
        if not isinstance(steps, list):
            steps = []

        normalized_steps = []
        for s in steps:
            if not isinstance(s, dict):
                continue
            normalized_steps.append({
                "skill": str(s.get("skill", "")),
                "input": s.get("input", {}) if isinstance(s.get("input"), dict) else {},
                "description": str(s.get("description", "")),
            })

        if not normalized_steps:
            return self._fallback_plan(user_input)

        return {"steps": normalized_steps}

    def _fallback_plan(self, user_input: str) -> dict:
        return {
            "steps": [
                {
                    "skill": "",
                    "input": {},
                    "description": user_input[:200],
                }
            ]
        }
