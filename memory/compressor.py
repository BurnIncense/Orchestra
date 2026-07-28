"""
对话压缩 — 把多轮对话摘要合并成长期记忆
"""

import logging

logger = logging.getLogger("orchestra.memory.compressor")


class DialogueCompressor:
    """对话压缩器"""

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def compress(self, messages: list[dict], existing_summary: str = "") -> str:
        """把 messages 压缩合并成一段摘要"""
        if not messages:
            return existing_summary

        dialogue_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages
        )

        if existing_summary:
            prompt = (
                "以下是之前的对话摘要和新的对话内容，请将它们合并成一段简洁连贯的摘要，"
                "保留关键信息和上下文：\n\n"
                f"[之前的摘要]\n{existing_summary}\n\n"
                f"[新的对话]\n{dialogue_text}\n\n"
                "请输出合并后的摘要："
            )
        else:
            prompt = (
                "请将以下对话内容总结成一段简洁连贯的摘要，保留关键信息和上下文：\n\n"
                f"{dialogue_text}\n\n"
                "请输出摘要："
            )

        system = (
            "你是一个对话摘要助手。你的任务是将多轮对话压缩成简洁、准确的摘要，"
            "保留关键事实、用户偏好和重要的上下文信息。不要添加原始对话中没有的内容。"
        )

        try:
            if hasattr(self.llm_client, "chat"):
                result = self.llm_client.chat(
                    prompt=prompt,
                    system=system,
                    max_tokens=1024,
                    temperature=0.3,
                )
                if isinstance(result, dict):
                    return result.get("content", "").strip()
                return str(result).strip()
        except Exception as e:
            logger.error(f"对话压缩调用失败: {e}")

        if existing_summary:
            return f"{existing_summary}\n---\n{dialogue_text}"
        return dialogue_text
