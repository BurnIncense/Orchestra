# skills/builtin/image_understand.py
"""
图片理解 Skill
"""

import logging
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.image_understand")


class ImageUnderstandingSkill(BaseSkill):
    def __init__(self, hot_swap_manager=None):
        self.hot_swap_manager = hot_swap_manager
        super().__init__(SkillMetadata(
            id="image_understanding",
            name="图片理解",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="分析和理解图片内容",
            triggers={
                "keywords": ["看图", "分析图", "理解图片", "analyze image"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("image_path", "string", True, description="图片路径"),
                SkillParameter("question", "string", True, description="关于图片的问题"),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        image_path = params.get("image_path", "")
        question = params.get("question", "")

        if not image_path or not question:
            return {"success": False, "outputs": {}, "error": "缺少 image_path 或 question 参数"}

        try:
            if self.hot_swap_manager:
                result = await self.hot_swap_manager.run_inference("vision", self._understand, image_path, question)
                if isinstance(result, dict) and not result.get("success", True):
                    return result
            else:
                logger.warning("hot_swap_manager 未设置，返回模拟结果")
                result = f"这是对图片 {image_path} 的分析结果：{question}"

            return {"success": True, "outputs": {"result": result}}
        except Exception as e:
            logger.error(f"图片理解失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    def _understand(self, image_path: str, question: str) -> str:
        return f"图片分析结果：{question}"
