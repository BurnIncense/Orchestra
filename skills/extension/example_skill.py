# skills/extension/example_skill.py
"""
扩展示例 Skill — 最小模板
"""

from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter


class ExampleSkill(BaseSkill):
    def __init__(self):
        super().__init__(SkillMetadata(
            id="example_skill",
            name="示例技能",
            version="1.0.0",
            category=SkillCategory.EXTENSION,
            description="这是一个扩展示例",
            triggers={"keywords": ["示例", "example"], "intent_types": []},
            parameters=[SkillParameter("input_text", "string", True, description="输入文本")],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        return {"success": True, "outputs": {"result": f"处理: {params['input_text']}"}}


def create_skill(**kwargs):
    return ExampleSkill()
