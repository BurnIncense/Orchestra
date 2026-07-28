# skills/builtin/video_gen.py
"""
视频生成 Skill
"""

import os
import uuid
import logging
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.video_gen")


class VideoGenerationSkill(BaseSkill):
    def __init__(self, hot_swap_manager=None, output_dir: str = "./data/outputs"):
        self.hot_swap_manager = hot_swap_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        super().__init__(SkillMetadata(
            id="video_generation",
            name="视频生成",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="根据文本提示生成视频",
            triggers={
                "keywords": ["视频", "生成视频", "做视频", "video", "generate video"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("prompt", "string", True, "视频描述"),
                SkillParameter("num_frames", "int", False, "帧数", 45),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        prompt = params.get("prompt", "")
        num_frames = params.get("num_frames", 45)

        if not prompt:
            return {"success": False, "outputs": {}, "error": "缺少 prompt 参数"}

        try:
            if self.hot_swap_manager:
                result = await self.hot_swap_manager.run_inference("video", self._generate, prompt, num_frames)
                if isinstance(result, dict) and not result.get("success", True):
                    return result
            else:
                logger.warning("hot_swap_manager 未设置，返回模拟结果")
                result = self._generate_mock(prompt, num_frames)

            return {"success": True, "outputs": {"video_path": result}}
        except Exception as e:
            logger.error(f"视频生成失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    def _generate(self, prompt: str, num_frames: int) -> str:
        filename = f"video_{uuid.uuid4().hex[:12]}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        return filepath

    def _generate_mock(self, prompt: str, num_frames: int) -> str:
        filename = f"video_{uuid.uuid4().hex[:12]}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        return filepath
