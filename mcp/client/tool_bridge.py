"""
MCP 工具桥接 — 将 MCP 工具注册为 Skill
所有外部依赖均采用延迟导入，mcp 包未安装时也可 import
"""

import logging
from typing import Any

logger = logging.getLogger("orchestra.mcp.bridge")


class MCPBridgeSkill:
    """桥接 MCP 工具到 Skill 系统的包装类"""

    def __init__(self, mcp_client: Any, server_name: str, tool: Any):
        self._mcp_client = mcp_client
        self._server_name = server_name
        self._tool = tool
        self._tool_name = getattr(tool, "name", str(tool))

        skill_id = f"mcp:{server_name}:{self._tool_name}"
        try:
            from skills.base import SkillMetadata, SkillCategory, SkillParameter

            params = []
            tool_input_schema = getattr(tool, "inputSchema", None)
            if tool_input_schema and isinstance(tool_input_schema, dict):
                properties = tool_input_schema.get("properties", {})
                required = tool_input_schema.get("required", [])
                for pname, pschema in properties.items():
                    params.append(SkillParameter(
                        name=pname,
                        type=pschema.get("type", "string"),
                        required=pname in required,
                        description=pschema.get("description", ""),
                    ))

            self.metadata = SkillMetadata(
                id=skill_id,
                name=self._tool_name,
                version="1.0.0",
                category=SkillCategory.MCP,
                description=getattr(tool, "description", ""),
                triggers={
                    "keywords": [self._tool_name, f"mcp:{server_name}"],
                    "intent_types": [],
                },
                parameters=params,
                permissions=[f"mcp:{server_name}:{self._tool_name}"],
            )
        except Exception:
            self.metadata = None

    async def execute(self, params: dict, context: dict = None) -> dict:
        return await self._mcp_client.call_tool(
            self._server_name, self._tool_name, params
        )

    def validate_params(self, params: dict) -> tuple:
        return True, ""


def bridge_mcp_tools_to_skills(mcp_client, registry) -> int:
    """将发现的 MCP 工具桥接到 Skill 注册中心"""
    count = 0
    try:
        for server_name, tools in mcp_client.discovered_tools.items():
            for tool in tools:
                try:
                    skill = MCPBridgeSkill(mcp_client, server_name, tool)
                    if skill.metadata is not None:
                        registry.register(skill)
                        count += 1
                except Exception as e:
                    logger.warning(
                        f"桥接 MCP 工具失败 [{server_name}.{getattr(tool, 'name', '?')}]: {e}"
                    )
    except Exception as e:
        logger.warning(f"MCP 工具桥接失败: {e}")

    logger.info(f"已桥接 {count} 个 MCP 工具到 Skill")
    return count
