"""
统一路由器

规则：
1. 命名空间隔离（builtin / ext / wf / mcp）
2. 优先级路由（builtin > composite > extension > learned > mcp）
3. 自调用检测（加密 Token，非名称匹配）
4. 运行时调用栈循环检测
5. 显式指定（@namespace:id）
"""

import os
import uuid
import hashlib
import logging
from enum import IntEnum
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("orchestra.router")


class SkillSource(IntEnum):
    BUILTIN = 0
    COMPOSITE = 1
    EXTENSION = 2
    LEARNED = 3
    MCP_BRIDGE = 4


@dataclass
class RoutingDecision:
    skill_id: str
    source: SkillSource
    confidence: float
    is_mcp_bridge: bool = False
    mcp_server: str = ""
    mcp_tool: str = ""


class UnifiedRouter:
    def __init__(self, registry, mcp_client, agent_id: str = "orchestra"):
        self.registry = registry
        self.mcp_client = mcp_client
        self.agent_id = agent_id
        self._instance_token = self._generate_instance_token()
        self._self_tokens: set[str] = {self._instance_token}
        self._call_stack: list[str] = []
        self._max_depth = 10

    def _generate_instance_token(self) -> str:
        raw = f"{uuid.uuid4().hex}:{os.getpid()}:{id(self)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def register_self_token(self, token: str):
        self._self_tokens.add(token)

    def resolve(self, skill_id: str, context: dict = None,
                server_token: str = "") -> Optional[RoutingDecision]:
        if skill_id.startswith("@"):
            return self._resolve_explicit(skill_id)

        if self._is_self_call(skill_id, server_token):
            return None

        candidates = self._find_candidates(skill_id)
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.source)
        return candidates[0]

    def _resolve_explicit(self, skill_id: str) -> Optional[RoutingDecision]:
        parts = skill_id[1:].split(":")
        if parts[0] == "mcp" and len(parts) >= 3:
            server, tool = parts[1], ":".join(parts[2:])
            return RoutingDecision(
                skill_id=f"mcp:{server}:{tool}",
                source=SkillSource.MCP_BRIDGE,
                confidence=1.0,
                is_mcp_bridge=True,
                mcp_server=server,
                mcp_tool=tool,
            )
        else:
            sid = ":".join(parts[1:])
            skill = self.registry.get(sid)
            if skill:
                return RoutingDecision(
                    skill_id=sid,
                    source=self._get_source(skill),
                    confidence=1.0,
                )
        return None

    def _is_self_call(self, skill_id: str, server_token: str = "") -> bool:
        if skill_id in self._call_stack:
            return True
        if server_token and server_token in self._self_tokens:
            return True
        return False

    def _find_candidates(self, skill_id: str) -> list[RoutingDecision]:
        candidates = []
        skill = self.registry.get(skill_id)
        if skill:
            candidates.append(RoutingDecision(
                skill_id=skill_id,
                source=self._get_source(skill),
                confidence=1.0,
            ))
        for server_name, tools in self.mcp_client.discovered_tools.items():
            for tool in tools:
                if tool.name == skill_id:
                    candidates.append(RoutingDecision(
                        skill_id=f"mcp:{server_name}:{tool.name}",
                        source=SkillSource.MCP_BRIDGE,
                        confidence=0.9,
                        is_mcp_bridge=True,
                        mcp_server=server_name,
                        mcp_tool=tool.name,
                    ))
        return candidates

    def _get_source(self, skill) -> SkillSource:
        from skills.base import SkillCategory
        mapping = {
            SkillCategory.BUILTIN: SkillSource.BUILTIN,
            SkillCategory.COMPOSITE: SkillSource.COMPOSITE,
            SkillCategory.EXTENSION: SkillSource.EXTENSION,
            SkillCategory.LEARNED: SkillSource.LEARNED,
            SkillCategory.MCP: SkillSource.MCP_BRIDGE,
        }
        cat = skill.metadata.category
        if cat in mapping:
            return mapping[cat]
        cat_val = getattr(cat, "value", cat)
        for k, v in mapping.items():
            if k.value == cat_val:
                return v
        return SkillSource.EXTENSION

    def push_call(self, skill_id: str):
        if len(self._call_stack) >= self._max_depth:
            raise RecursionError(f"调用深度超过 {self._max_depth}")
        if skill_id in self._call_stack:
            cycle_start = self._call_stack.index(skill_id)
            cycle = self._call_stack[cycle_start:] + [skill_id]
            from core.dependency_graph import CyclicDependencyError
            raise CyclicDependencyError(f"循环: {' → '.join(cycle)}")
        self._call_stack.append(skill_id)

    def pop_call(self):
        if self._call_stack:
            self._call_stack.pop()

    def reset(self):
        self._call_stack.clear()

    async def call_skill(self, skill_id: str, params: dict,
                          context: dict = None) -> dict:
        decision = self.resolve(skill_id)
        if not decision:
            return {"success": False, "error": f"无法路由: {skill_id}"}

        self.push_call(skill_id)
        try:
            if decision.is_mcp_bridge:
                return await self.mcp_client.call_tool(
                    decision.mcp_server, decision.mcp_tool, params
                )
            else:
                skill = self.registry.get(decision.skill_id)
                if not skill:
                    return {"success": False, "error": f"Skill 不存在: {skill_id}"}
                return await skill.execute(params, context)
        finally:
            self.pop_call()
