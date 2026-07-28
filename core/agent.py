# core/agent.py
"""
Orchestra Agent v2.2 — 完整主循环
"""

import asyncio
import json
import logging
import time
from rich.console import Console

from models.llm_service import create_thinker, create_memory_llm
from models.hot_swap import HotSwapManager
from core.session import SessionManager
from core.router import UnifiedRouter
from core.saga import SagaEngine
from core.planner import TaskPlanner
from core.intent import IntentClassifier
from core.param_extractor import ParamExtractor
from core.dependency_graph import DependencyGraph, RuntimeCallGuard
from skills.registry import SkillRegistry
from skills.loader import SkillLoader
from skills.composer import SkillComposer
from skills.sandbox_v2 import ProcessIsolatedSandbox, SkillExecutionDispatcher, SandboxConfig
from mcp.client.manager import MCPClientManager
from mcp.client.tool_bridge import bridge_mcp_tools_to_skills
from utils.tracing import new_trace, tracer

logger = logging.getLogger("orchestra.agent")
console = Console()


class OrchestraAgent:
    def __init__(self, config: dict):
        self.config = config

        def _safe_port(value, default: int) -> int:
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    return default
            return default

        # LLM 服务
        thinker_cfg = config.get("models", {}).get("thinker", {})
        thinker_cfg.setdefault("port", _safe_port(config.get("ports", {}).get("thinker"), 8081))
        self.thinker = create_thinker(thinker_cfg)

        memory_cfg = config.get("models", {}).get("memory", {})
        memory_cfg.setdefault("port", _safe_port(config.get("ports", {}).get("memory"), 8082))
        self.memory_llm = create_memory_llm(memory_cfg)

        # GPU 管理
        self.hot_swap = HotSwapManager(config)

        # 会话管理
        self.session_manager = SessionManager(self.memory_llm)

        # Skill 系统
        self.registry = SkillRegistry("./skills")
        self.loader = SkillLoader(self.registry)
        self.composer = SkillComposer(self.registry)

        # 沙箱
        sandbox_cfg = SandboxConfig(**config.get("skills", {}).get("sandbox", {}))
        self.sandbox = ProcessIsolatedSandbox(sandbox_cfg)
        self.dispatcher = SkillExecutionDispatcher(self.sandbox)

        # MCP
        self.mcp_client = MCPClientManager(
            config.get("mcp", {}).get("client", {}).get("config_path", "./mcp/config/servers.yaml")
        )

        # 路由
        self.router = UnifiedRouter(self.registry, self.mcp_client)

        # Saga
        self.saga_engine = SagaEngine(self.router)

        # 核心组件
        self.planner = TaskPlanner(self.thinker)
        self.intent = IntentClassifier(self.thinker)
        self.param_extractor = ParamExtractor(self.thinker)
        self.dep_graph = DependencyGraph()

        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        console.print("\n  [bold]🎼 Orchestra v2.2 初始化中...[/bold]")

        # 加载 Skill
        self.registry.load_definitions()
        self._register_builtin_skills()
        self.loader.load_from_directory("./skills/extension")

        # 连接 MCP
        mcp_cfg = self.config.get("mcp", {}).get("client", {})
        if mcp_cfg.get("enabled", False):
            await self.mcp_client.connect_all()
            if mcp_cfg.get("bridge_to_skills", True):
                bridge_mcp_tools_to_skills(self.mcp_client, self.registry)

        # 注册工作流
        self._register_workflows()

        # 启动会话清理
        await self.session_manager.start_cleanup_loop()

        # 崩溃恢复
        incomplete = self.saga_engine.recover_incomplete()
        if incomplete:
            logger.warning(f"⚠️ 恢复 {len(incomplete)} 个未完成的 Saga")
            for state in incomplete:
                try:
                    await self.saga_engine.resume(state)
                except Exception as e:
                    logger.error(f"恢复失败: {e}")

        # 报告模型状态
        model_status = []
        if hasattr(self.thinker, 'is_available') and not self.thinker.is_available:
            model_status.append("Thinker(模拟)")
        else:
            model_status.append("Thinker(就绪)")
        if hasattr(self.memory_llm, 'is_available') and not self.memory_llm.is_available:
            model_status.append("Memory(模拟)")
        else:
            model_status.append("Memory(就绪)")

        self._initialized = True
        console.print(f"  [green]✅ 就绪[/green] | {' | '.join(model_status)} | Skill: {self.registry.count} | MCP: {len(self.mcp_client.connections)}\n")

    async def process(self, user_input: str, user_id: str = "default") -> str:
        # 获取 Session
        session = await self.session_manager.get_or_create(user_id)
        session.turn_count += 1

        # Trace
        trace_id = new_trace()
        session.current_trace_id = trace_id
        session.call_guard.reset()

        # 记忆
        session.memory.add_turn("user", user_input)

        # 意图
        intent = self.intent.classify(user_input, session.memory.get_context())

        # 执行
        context = session.get_context()
        if intent["type"] == "complex_task":
            response = await self._execute_complex_task(user_input, context)
        elif intent["type"] in ("image_generation", "video_generation", "multishot_video"):
            response = await self._execute_skill_flow(user_input, intent, context)
        else:
            response = self._chat(user_input, session)

        # 更新记忆
        session.memory.add_turn("assistant", response[:500])

        # 学习
        session.learner.record(intent.get("skill_id", ""), {}, {"success": True})

        # 释放 GPU
        self.hot_swap.unload_if_generation_done()

        # 定期保存
        if session.turn_count % 5 == 0:
            session.save()

        return response

    async def _execute_skill_flow(self, user_input: str, intent: dict, context: dict) -> str:
        matched = self.registry.find_by_trigger(user_input, intent["type"])
        if not matched:
            return self._chat(user_input, context.get("memory"))

        skill, score = matched[0]
        params = self.param_extractor.extract(user_input, skill.metadata.parameters)
        params = context["learner"].apply_preferences(skill.id, params)

        result = await self.dispatcher.execute(skill, params, context)

        if result.get("success"):
            summary = self.thinker.chat(
                prompt=f"用户：{user_input}\n结果：{json.dumps(result.get('outputs', {}), ensure_ascii=False)}\n简短描述：",
                max_tokens=200,
            )
            return summary["content"]
        return f"❌ 执行失败: {result.get('error')}"

    async def _execute_complex_task(self, user_input: str, context: dict) -> str:
        plan = self.planner.create_plan(user_input, context.get("memory", None))
        steps = [
            {"skill_id": s.get("skill", ""), "params": s.get("input", {}),
             "description": s.get("description", "")}
            for s in plan.get("steps", [])
        ]
        result = await self.saga_engine.execute("complex_task", steps, context)
        if result["success"]:
            summary = self.thinker.chat(
                prompt=f"任务：{user_input}\n结果：{json.dumps(result, ensure_ascii=False)}\n总结：",
                max_tokens=1024,
            )
            return summary["content"]
        return f"❌ 任务失败: {result['error']}（已自动回滚）"

    def _chat(self, user_input: str, session_or_memory) -> str:
        memory = session_or_memory if hasattr(session_or_memory, 'get_context') else session_or_memory
        ctx = memory.get_context() if hasattr(memory, 'get_context') else ""
        result = self.thinker.chat(
            prompt=user_input,
            system=f"你是 Orchestra，全能 AI Agent。\n\n上下文：\n{ctx}",
            history=memory.get_recent_messages(6) if hasattr(memory, 'get_recent_messages') else [],
        )
        return result["content"]

    def _register_builtin_skills(self):
        from skills.builtin.image_gen import ImageGenerationSkill
        from skills.builtin.image_understand import ImageUnderstandingSkill
        from skills.builtin.video_gen import VideoGenerationSkill
        from skills.builtin.multishot_video import MultiShotVideoSkill
        from skills.builtin.code_exec import CodeExecutionSkill
        from skills.builtin.web_search import WebSearchSkill

        for skill in [
            ImageGenerationSkill(self.hot_swap, "./data/outputs"),
            ImageUnderstandingSkill(self.hot_swap),
            VideoGenerationSkill(self.hot_swap, "./data/outputs"),
            MultiShotVideoSkill(self.hot_swap, "./data/outputs"),
            CodeExecutionSkill(self.thinker),
            WebSearchSkill(),
        ]:
            self.registry.register(skill)

    def _register_workflows(self):
        from skills.composer import create_video_story_workflow
        wf = create_video_story_workflow()
        self.composer.register_workflow(wf)
        composite = self.composer.create_composite_skill(wf)
        self.registry.register(composite)

    async def shutdown(self):
        await self.session_manager.shutdown()
        await self.mcp_client.disconnect_all()
        self.hot_swap.unload_if_generation_done()
        tracer.flush()
