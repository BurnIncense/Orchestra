"""
参数提取器 — 从用户输入中提取 Skill 所需的参数
"""

import json
import logging
import re

logger = logging.getLogger("orchestra.param_extractor")


class ParamExtractor:
    def __init__(self, llm_client):
        self.llm = llm_client

    def extract(self, user_input: str, parameters: list) -> dict:
        if not parameters:
            return {}

        if not user_input or not user_input.strip():
            return {}

        llm_available = self._check_llm_available()

        if llm_available:
            try:
                return self._extract_with_llm(user_input, parameters)
            except Exception as e:
                logger.warning(f"LLM 参数提取失败，返回空字典: {e}")

        return {}

    def _check_llm_available(self) -> bool:
        try:
            if hasattr(self.llm, "is_available"):
                return self.llm.is_available()
        except Exception:
            pass
        return False

    def _extract_with_llm(self, user_input: str, parameters: list) -> dict:
        param_descriptions = []
        for p in parameters:
            if hasattr(p, "name"):
                name = p.name
                ptype = p.type
                required = p.required
                desc = p.description
            elif isinstance(p, dict):
                name = p.get("name", "")
                ptype = p.get("type", "str")
                required = p.get("required", False)
                desc = p.get("description", "")
            else:
                continue
            req_mark = " (必填)" if required else ""
            param_descriptions.append(f"- {name} ({ptype}){req_mark}: {desc}")

        prompt = f"""你是一个参数提取专家。请从用户输入中提取以下参数。

用户输入：{user_input}

需要提取的参数：
{chr(10).join(param_descriptions)}

请以 JSON 格式返回提取结果，格式如下：
{{"param_name": value, ...}}

要求：
- 只返回能够从用户输入中明确提取的参数
- 无法确定的参数不要包含在结果中
- 值的类型要匹配参数类型（字符串用引号，数字不要引号，布尔值用 true/false）
- 如果用户输入是一个列表或多个值，用数组表示

只返回 JSON，不要其他内容。"""

        result = self.llm.chat(
            prompt=prompt,
            system="你是一个精确的参数提取器。",
            max_tokens=512,
            temperature=0.1,
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

        if not isinstance(parsed, dict):
            return {}

        valid_names = set()
        for p in parameters:
            if hasattr(p, "name"):
                valid_names.add(p.name)
            elif isinstance(p, dict):
                valid_names.add(p.get("name", ""))

        filtered = {}
        for k, v in parsed.items():
            if k in valid_names:
                filtered[k] = v

        return filtered
