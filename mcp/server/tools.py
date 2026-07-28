"""
MCP 工具定义 — 从 orchestra_server.py 提取的工具函数存根
"""

import logging
from typing import Any

logger = logging.getLogger("orchestra.mcp.tools")


async def generate_image(agent: Any, prompt: str, style: str = "realistic",
                         size: str = "384x384") -> str:
    result = await agent.router.call_skill("image_generation", {
        "prompt": prompt, "style": style, "size": size
    })
    if result["success"]:
        return f"✅ 图片已生成: {result['outputs']['image_path']}"
    return f"❌ 失败: {result.get('error')}"


async def generate_video(agent: Any, prompt: str,
                         num_frames: int = 45) -> str:
    result = await agent.router.call_skill("video_generation", {
        "prompt": prompt, "num_frames": num_frames
    })
    if result["success"]:
        return f"✅ 视频已生成: {result['outputs']['video_path']}"
    return f"❌ 失败: {result.get('error')}"


async def generate_multishot_video(agent: Any, shots: list[dict]) -> str:
    result = await agent.router.call_skill("multishot_video", {"shots": shots})
    if result["success"]:
        return f"✅ 多镜头视频: {result['outputs']['video_path']}"
    return f"❌ 失败: {result.get('error')}"


async def understand_image(agent: Any, image_path: str, question: str) -> str:
    result = await agent.router.call_skill("image_understanding", {
        "image_path": image_path, "question": question
    })
    return result.get("outputs", {}).get("analysis", result.get("error", ""))


async def chat(agent: Any, message: str) -> str:
    return await agent.process(message, user_id="mcp_client")


async def analyze_document(agent: Any, file_path: str,
                           question: str = "总结核心内容") -> str:
    return await agent.process(
        f"分析文档 {file_path}：{question}", user_id="mcp_client"
    )
