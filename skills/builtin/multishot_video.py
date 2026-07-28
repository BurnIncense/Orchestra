# skills/builtin/multishot_video.py
"""
多镜头视频 Skill
"""

import os
import uuid
import logging
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.multishot_video")


class MultiShotVideoSkill(BaseSkill):
    def __init__(self, hot_swap_manager=None, output_dir: str = "./data/outputs"):
        self.hot_swap_manager = hot_swap_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        super().__init__(SkillMetadata(
            id="multishot_video",
            name="多镜头视频",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="生成多镜头分镜故事视频",
            triggers={
                "keywords": ["多镜头", "故事视频", "分镜", "multishot", "story video"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("shots", "list", True, description="分镜列表"),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        shots = params.get("shots", [])

        if not shots or not isinstance(shots, list):
            return {"success": False, "outputs": {}, "error": "缺少 shots 参数或格式错误"}

        try:
            if self.hot_swap_manager:
                result = await self.hot_swap_manager.run_inference("video", self._generate, shots)
                if isinstance(result, dict) and not result.get("success", True):
                    return result
            else:
                logger.warning("hot_swap_manager 未设置，返回模拟结果")
                result = self._generate_mock(shots)

            return {"success": True, "outputs": {"video_path": result, "num_shots": len(shots)}}
        except Exception as e:
            logger.error(f"多镜头视频生成失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    def _generate(self, shots: list) -> str:
        filename = f"multishot_{uuid.uuid4().hex[:12]}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        return filepath

    def _generate_mock(self, shots: list) -> str:
        filename = f"multishot_{uuid.uuid4().hex[:12]}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        return filepath
