# skills/learner.py
"""
Skill 学习器 — 记录调用历史，学习用户偏好
"""

import logging
from memory import persistence

logger = logging.getLogger("orchestra.learner")


class SkillLearner:
    def __init__(self, memory_llm=None, persist_path: str = "./data/memory/preferences.json"):
        self.memory_llm = memory_llm
        self.persist_path = persist_path
        self.preferences: dict = {}
        self._records: list = []
        self._load()

    def record(self, skill_id: str, params: dict, result: dict) -> None:
        self._records.append({
            "skill_id": skill_id,
            "params": dict(params),
            "result": result,
        })

        if skill_id not in self.preferences:
            self.preferences[skill_id] = {"params": {}, "count": 0}

        pref = self.preferences[skill_id]
        pref["count"] += 1

        for key, value in params.items():
            if isinstance(value, (str, int, float, bool)):
                pref["params"][key] = value

        self._save()
        logger.debug(f"已记录 Skill 调用: {skill_id} (累计 {pref['count']} 次)")

    def apply_preferences(self, skill_id: str, params: dict) -> dict:
        merged = dict(params)
        pref = self.preferences.get(skill_id)
        if pref:
            for key, value in pref["params"].items():
                if key not in merged:
                    merged[key] = value
        return merged

    def _save(self) -> None:
        try:
            persistence.save_json(self.persist_path, self.preferences)
        except Exception as e:
            logger.warning(f"保存偏好失败: {e}")

    def _load(self) -> None:
        try:
            data = persistence.load_json(self.persist_path, {})
            if isinstance(data, dict):
                self.preferences = data
        except Exception as e:
            logger.warning(f"加载偏好失败: {e}")
