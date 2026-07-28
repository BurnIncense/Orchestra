import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orchestra.skills.registry")


class SkillRegistry:
    def __init__(self, definitions_dir: str = "./skills/definitions"):
        self.definitions_dir = Path(definitions_dir)
        self._skills: dict = {}
        self._keyword_index: dict = {}
        self._intent_index: dict = {}
        self.load_definitions()

    def register(self, skill) -> None:
        skill_id = skill.metadata.id
        self._skills[skill_id] = skill

        triggers = skill.metadata.triggers or {}
        for keyword in triggers.get("keywords", []):
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = []
            if skill_id not in self._keyword_index[keyword]:
                self._keyword_index[keyword].append(skill_id)

        intent_types = triggers.get("intent_types", [])
        for it in intent_types:
            if it not in self._intent_index:
                self._intent_index[it] = []
            if skill_id not in self._intent_index[it]:
                self._intent_index[it].append(skill_id)

        logger.debug(f"已注册 Skill: {skill_id}")

    def get(self, skill_id: str):
        return self._skills.get(skill_id)

    def find_by_trigger(self, user_input: str, intent_type: str = "") -> list:
        scores: dict = {}

        if user_input:
            for keyword, skill_ids in self._keyword_index.items():
                if keyword.lower() in user_input.lower():
                    for sid in skill_ids:
                        scores[sid] = scores.get(sid, 0.0) + 1.0

        if intent_type:
            for it, skill_ids in self._intent_index.items():
                if it == intent_type:
                    for sid in skill_ids:
                        scores[sid] = scores.get(sid, 0.0) + 2.0

        results = []
        for sid, score in scores.items():
            skill = self._skills.get(sid)
            if skill:
                results.append((skill, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def load_definitions(self) -> None:
        if not self.definitions_dir.exists():
            logger.debug(f"definitions 目录不存在: {self.definitions_dir}")
            return
        try:
            for yaml_file in self.definitions_dir.glob("*.yaml"):
                logger.debug(f"发现 Skill 定义: {yaml_file.name}")
        except Exception as e:
            logger.warning(f"加载 definitions 失败: {e}")

    @property
    def count(self) -> int:
        return len(self._skills)

    def status_report(self) -> str:
        lines = [
            f"SkillRegistry 状态报告",
            f"  已注册 Skill: {self.count}",
            f"  关键词索引: {len(self._keyword_index)} 个关键词",
            f"  意图索引: {len(self._intent_index)} 个意图类型",
            f"  定义目录: {self.definitions_dir}",
        ]
        if self._skills:
            lines.append("  已注册 Skill 列表:")
            for sid, skill in self._skills.items():
                lines.append(f"    - {sid} ({skill.metadata.category.value})")
        return "\n".join(lines)
