"""
意图识别器 — 将用户输入分类到对应意图类型
"""

import json
import logging
import re

logger = logging.getLogger("orchestra.intent")


INTENT_KEYWORDS = {
    "image_generation": [
        "画图", "生成图片", "生成图像", "画一张", "创建图片", "图片生成",
        "图像生成", "draw", "generate image", "create image", "插画",
    ],
    "video_generation": [
        "生成视频", "做视频", "视频生成", "创建视频", "generate video",
        "create video", "动画", "动画片",
    ],
    "multishot_video": [
        "多镜头", "多分镜", "分镜", "多场景", "电影感", "多镜头视频",
        "story video", "multi-shot",
    ],
    "complex_task": [
        "帮我做", "执行任务", "处理", "分析并", "然后", "接着",
        "完成以下", "步骤", "任务", "帮我分析", "帮我处理",
    ],
    "document_analysis": [
        "分析文档", "文档分析", "读取文档", "解析文档", "总结文档",
        "document", "read pdf", "分析文件", "阅读文档",
    ],
}


class IntentClassifier:
    def __init__(self, llm_client):
        self.llm = llm_client

    def classify(self, user_input: str, context: str = "") -> dict:
        if not user_input or not user_input.strip():
            return {"type": "chat", "skill_id": "", "confidence": 0.9}

        llm_available = self._check_llm_available()

        if llm_available:
            try:
                return self._classify_with_llm(user_input, context)
            except Exception as e:
                logger.warning(f"LLM 意图识别失败，降级到规则匹配: {e}")

        return self._classify_by_keywords(user_input)

    def _check_llm_available(self) -> bool:
        try:
            if hasattr(self.llm, "is_available"):
                return self.llm.is_available()
        except Exception:
            pass
        return False

    def _classify_with_llm(self, user_input: str, context: str) -> dict:
        intent_list = [
            "chat - 日常对话、闲聊、问答",
            "image_generation - 生成单张图片、插画",
            "video_generation - 生成单个视频片段",
            "multishot_video - 生成多镜头/分镜视频",
            "complex_task - 需要多步执行的复杂任务",
            "document_analysis - 分析、总结、阅读文档",
        ]

        prompt = f"""你是一个意图分类器。请根据用户输入判断其意图类型。

可选意图类型：
{chr(10).join(intent_list)}

用户输入：{user_input}
上下文：{context[:1000] if context else "无"}

请以 JSON 格式返回结果，格式如下：
{{"type": "意图类型", "skill_id": "匹配的skill_id或空字符串", "confidence": 0.0-1.0}}

只返回 JSON，不要其他内容。"""

        result = self.llm.chat(
            prompt=prompt,
            system="你是一个精确的意图分类器。",
            max_tokens=200,
            temperature=0.1,
        )

        content = result.get("content", "").strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    parsed = {}
            else:
                parsed = {}

        intent_type = parsed.get("type", "chat")
        valid_types = {"chat", "image_generation", "video_generation",
                       "multishot_video", "complex_task", "document_analysis"}
        if intent_type not in valid_types:
            intent_type = "chat"

        return {
            "type": intent_type,
            "skill_id": parsed.get("skill_id", ""),
            "confidence": float(parsed.get("confidence", 0.7)),
        }

    def _classify_by_keywords(self, user_input: str) -> dict:
        input_lower = user_input.lower()

        scores = {}
        for intent_type, keywords in INTENT_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw.lower() in input_lower:
                    score += 1.0
            if score > 0:
                scores[intent_type] = score

        if not scores:
            return {"type": "chat", "skill_id": "", "confidence": 0.8}

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        confidence = min(best_score / 3.0, 0.95)

        return {"type": best_type, "skill_id": "", "confidence": confidence}
