# skills/builtin/image_gen.py
"""
图片生成 Skill
"""

import os
import uuid
import logging
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.image_gen")


class ImageGenerationSkill(BaseSkill):
    def __init__(self, hot_swap_manager=None, output_dir: str = "./data/outputs"):
        self.hot_swap_manager = hot_swap_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        super().__init__(SkillMetadata(
            id="image_generation",
            name="图片生成",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="根据文本提示生成图片",
            triggers={
                "keywords": ["画", "图片", "图像", "生成图", "image", "generate image"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("prompt", "string", True, "图片描述"),
                SkillParameter("style", "string", False, "图片风格", "realistic"),
                SkillParameter("size", "string", False, "图片尺寸", "384x384"),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        prompt = params.get("prompt", "")
        style = params.get("style", "realistic")
        size = params.get("size", "384x384")

        if not prompt:
            return {"success": False, "outputs": {}, "error": "缺少 prompt 参数"}

        try:
            if self.hot_swap_manager:
                result = await self.hot_swap_manager.run_inference("vision", self._generate, prompt, style, size)
                if isinstance(result, dict) and not result.get("success", True):
                    return result
            else:
                logger.warning("hot_swap_manager 未设置，返回模拟结果")
                result = self._generate_mock(prompt, style, size)

            return {"success": True, "outputs": {"image_path": result}}
        except Exception as e:
            logger.error(f"图片生成失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    def _generate(self, prompt: str, style: str, size: str) -> str:
        filename = f"image_{uuid.uuid4().hex[:12]}.png"
        filepath = os.path.join(self.output_dir, filename)
        return filepath

    def _generate_mock(self, prompt: str, style: str, size: str) -> str:
        filename = f"image_{uuid.uuid4().hex[:12]}.png"
        filepath = os.path.join(self.output_dir, filename)
        return filepath
