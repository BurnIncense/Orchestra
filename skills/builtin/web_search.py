# skills/builtin/web_search.py
"""
网页搜索 Skill
"""

import logging
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.web_search")


class WebSearchSkill(BaseSkill):
    def __init__(self):
        super().__init__(SkillMetadata(
            id="web_search",
            name="网页搜索",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="在互联网上搜索信息",
            triggers={
                "keywords": ["搜索", "search", "找", "web", "google"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("query", "string", True, description="搜索关键词"),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        query = params.get("query", "")

        if not query:
            return {"success": False, "outputs": {}, "error": "缺少 query 参数"}

        try:
            results = self._mock_search(query)
            return {"success": True, "outputs": {"results": results}}
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    def _mock_search(self, query: str) -> list:
        return [
            {
                "title": f"关于 {query} 的搜索结果 1",
                "snippet": f"这是与 '{query}' 相关的搜索结果摘要...",
                "url": f"https://example.com/search?q={query}&r=1",
            },
            {
                "title": f"关于 {query} 的搜索结果 2",
                "snippet": f"更多关于 '{query}' 的信息...",
                "url": f"https://example.com/search?q={query}&r=2",
            },
            {
                "title": f"关于 {query} 的搜索结果 3",
                "snippet": f"'{query}' 的详细资料...",
                "url": f"https://example.com/search?q={query}&r=3",
            },
        ]
