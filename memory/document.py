"""
文档处理 — 加载、分块、分析
"""

import logging

logger = logging.getLogger("orchestra.memory.document")


class DocumentProcessor:
    """文档处理器"""

    def __init__(self, llm_client=None, max_context: int = 262144):
        self.llm_client = llm_client
        self.max_context = max_context

    def load_document(self, file_path: str) -> str:
        """读取文件内容"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def chunk_text(self, text: str, chunk_size: int = 4000, overlap: int = 200) -> list[str]:
        """将文本分块"""
        if not text:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap

        return chunks

    async def analyze(self, file_path: str, question: str = "总结核心内容") -> str:
        """加载文档，分块，调用 LLM 分析"""
        try:
            text = self.load_document(file_path)
        except Exception as e:
            return f"读取文件失败: {e}"

        chunks = self.chunk_text(text)

        if not self.llm_client:
            if not chunks:
                return "文档为空"
            preview = chunks[0][:500]
            return f"文档加载成功，共 {len(chunks)} 个分块。预览:\n{preview}..."

        try:
            summaries = []
            for i, chunk in enumerate(chunks):
                prompt = (
                    f"请阅读以下文档片段（第 {i + 1}/{len(chunks)} 块），"
                    f"并回答问题: {question}\n\n"
                    f"文档片段:\n{chunk}\n\n"
                    f"请给出回答:"
                )
                system = (
                    "你是一个文档分析助手。请基于提供的文档内容准确回答问题，"
                    "不要编造文档中没有的信息。"
                )

                if hasattr(self.llm_client, "chat"):
                    result = self.llm_client.chat(
                        prompt=prompt,
                        system=system,
                        max_tokens=1024,
                        temperature=0.3,
                    )
                    if isinstance(result, dict):
                        summaries.append(result.get("content", "").strip())
                    else:
                        summaries.append(str(result).strip())

            if len(summaries) == 1:
                return summaries[0]

            combined = "\n\n".join(summaries)
            if len(summaries) > 1 and hasattr(self.llm_client, "chat"):
                merge_prompt = (
                    f"以下是对文档多个分块的分析结果，请合并成一个完整的回答，"
                    f"回答问题: {question}\n\n"
                    f"各分块分析结果:\n{combined}\n\n"
                    f"请给出合并后的完整回答:"
                )
                result = self.llm_client.chat(
                    prompt=merge_prompt,
                    max_tokens=2048,
                    temperature=0.3,
                )
                if isinstance(result, dict):
                    return result.get("content", "").strip()
                return str(result).strip()

            return combined

        except Exception as e:
            logger.error(f"文档分析失败: {e}")
            return f"分析过程中出错: {e}"
