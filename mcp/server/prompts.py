"""
MCP 提示词模板
"""


async def image_prompt_optimizer(description: str) -> str:
    return (
        "将以下描述优化为英文图片生成提示词（含主体/场景/光影/风格/构图）：\n"
        f"{description}"
    )


async def video_storyboard(story: str) -> str:
    return (
        "将以下故事转化为 3-5 镜头的分镜脚本（JSON：prompt/duration/camera）：\n"
        f"{story}"
    )
