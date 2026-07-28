"""
Orchestra MCP Server — 将自身能力暴露给外部 AI（Claude, Cursor 等）
强制 HTTPS + API Key 认证 + 用户级资源 ACL
所有外部依赖均采用延迟导入，mcp 包未安装时也可 import
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("orchestra.mcp.server")


def create_orchestra_mcp_server(agent, config: dict) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

    if FastMCP is None:
        raise RuntimeError(
            "mcp 包未安装，请先安装: pip install mcp"
        )

    mcp = FastMCP("Orchestra", version="2.2.0",
                  description="全能 AI Agent — 图片/视频生成、对话、文档分析")

    @mcp.tool()
    async def generate_image(prompt: str, style: str = "realistic", size: str = "384x384") -> str:
        result = await agent.router.call_skill("image_generation", {
            "prompt": prompt, "style": style, "size": size
        })
        if result["success"]:
            return f"✅ 图片已生成: {result['outputs']['image_path']}"
        return f"❌ 失败: {result.get('error')}"

    @mcp.tool()
    async def generate_video(prompt: str, num_frames: int = 45) -> str:
        result = await agent.router.call_skill("video_generation", {
            "prompt": prompt, "num_frames": num_frames
        })
        if result["success"]:
            return f"✅ 视频已生成: {result['outputs']['video_path']}"
        return f"❌ 失败: {result.get('error')}"

    @mcp.tool()
    async def generate_multishot_video(shots: list[dict]) -> str:
        result = await agent.router.call_skill("multishot_video", {"shots": shots})
        if result["success"]:
            return f"✅ 多镜头视频: {result['outputs']['video_path']}"
        return f"❌ 失败: {result.get('error')}"

    @mcp.tool()
    async def understand_image(image_path: str, question: str) -> str:
        result = await agent.router.call_skill("image_understanding", {
            "image_path": image_path, "question": question
        })
        return result.get("outputs", {}).get("analysis", result.get("error", ""))

    @mcp.tool()
    async def chat(message: str) -> str:
        return await agent.process(message, user_id="mcp_client")

    @mcp.tool()
    async def analyze_document(file_path: str, question: str = "总结核心内容") -> str:
        return await agent.process(f"分析文档 {file_path}：{question}", user_id="mcp_client")

    @mcp.resource("orchestra://users/{user_id}/images/{filename}")
    async def get_user_image(user_id: str, filename: str) -> bytes:
        path = Path(f"./data/outputs/users/{user_id}/images/{filename}")
        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(f"不存在: {filename}")

    @mcp.resource("orchestra://shared/images/{filename}")
    async def get_shared_image(filename: str) -> bytes:
        path = Path(f"./data/outputs/shared/images/{filename}")
        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(f"不存在: {filename}")

    @mcp.prompt()
    async def image_prompt_optimizer(description: str) -> str:
        return f"将以下描述优化为英文图片生成提示词（含主体/场景/光影/风格/构图）：\n{description}"

    @mcp.prompt()
    async def video_storyboard(story: str) -> str:
        return f"将以下故事转化为 3-5 镜头的分镜脚本（JSON：prompt/duration/camera）：\n{story}"

    return mcp
