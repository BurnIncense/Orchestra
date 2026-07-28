# skills/composer.py
"""
Skill 组合器 — 将多个 Skill 组合成工作流
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("orchestra.composer")


class CyclicDependencyError(Exception):
    pass


@dataclass
class SkillStep:
    skill_id: str
    params: dict = field(default_factory=dict)
    description: str = ""
    parallel: bool = False
    timeout: float = 300.0


@dataclass
class Workflow:
    id: str
    name: str
    description: str = ""
    steps: list = field(default_factory=list)


class SkillComposer:
    def __init__(self, registry=None):
        self.registry = registry
        self._workflows: dict[str, Workflow] = {}

    def _check_cycle(self, wf_id: str, visiting: set, visited: set) -> None:
        if wf_id in visiting:
            raise CyclicDependencyError(f"检测到循环依赖: {wf_id}")
        if wf_id in visited:
            return
        visiting.add(wf_id)
        wf = self._workflows.get(wf_id)
        if wf:
            for step in wf.steps:
                if step.skill_id.startswith("workflow:"):
                    ref_id = step.skill_id[len("workflow:"):]
                    self._check_cycle(ref_id, visiting, visited)
        visiting.discard(wf_id)
        visited.add(wf_id)

    def register_workflow(self, wf: Workflow) -> None:
        if wf.id in self._workflows:
            logger.warning(f"工作流已存在，将覆盖: {wf.id}")
        self._workflows[wf.id] = wf
        visited = set()
        for existing_id in self._workflows:
            self._check_cycle(existing_id, set(), visited)
        logger.debug(f"已注册工作流: {wf.id}")

    def get_workflow(self, wf_id: str) -> Optional[Workflow]:
        return self._workflows.get(wf_id)

    async def execute_workflow(self, wf_id: str, params: dict, context: dict = None) -> dict:
        wf = self._workflows.get(wf_id)
        if not wf:
            return {"success": False, "error": f"工作流不存在: {wf_id}"}
        context = context or {}
        step_outputs: dict = {}
        sequential_steps = [s for s in wf.steps if not s.parallel]
        parallel_groups: list[list] = []
        current_group: list = []
        for step in wf.steps:
            if step.parallel:
                current_group.append(step)
            else:
                if current_group:
                    parallel_groups.append(current_group)
                    current_group = []
        if current_group:
            parallel_groups.append(current_group)

        try:
            for step in sequential_steps:
                result = await self._execute_step(step, params, context, step_outputs)
                if not result.get("success", False):
                    return {"success": False, "error": f"步骤失败 [{step.skill_id}]: {result.get('error', '')}"}
                step_outputs[step.skill_id] = result.get("outputs", {})

            for group in parallel_groups:
                tasks = [self._execute_step(step, params, context, step_outputs) for step in group]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for step, result in zip(group, results):
                    if isinstance(result, Exception):
                        return {"success": False, "error": f"步骤异常 [{step.skill_id}]: {str(result)}"}
                    if not result.get("success", False):
                        return {"success": False, "error": f"步骤失败 [{step.skill_id}]: {result.get('error', '')}"}
                    step_outputs[step.skill_id] = result.get("outputs", {})

            return {"success": True, "outputs": step_outputs}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_step(self, step: SkillStep, workflow_params: dict,
                            context: dict, step_outputs: dict) -> dict:
        if not self.registry:
            return {"success": False, "error": "SkillComposer 未绑定 registry"}

        skill = self.registry.get(step.skill_id)
        if not skill:
            return {"success": False, "error": f"Skill 不存在: {step.skill_id}"}

        merged_params = dict(workflow_params)
        for key, value in step.params.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                ref_path = value[2:-1]
                parts = ref_path.split(".")
                ref_val = step_outputs
                for p in parts:
                    if isinstance(ref_val, dict):
                        ref_val = ref_val.get(p)
                    else:
                        ref_val = None
                        break
                if ref_val is not None:
                    merged_params[key] = ref_val
            else:
                merged_params[key] = value

        try:
            result = await asyncio.wait_for(
                skill.execute(merged_params, context),
                timeout=step.timeout,
            )
            return result
        except asyncio.TimeoutError:
            return {"success": False, "error": f"步骤超时（>{step.timeout}s）"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_composite_skill(self, wf: Workflow):
        from skills.base import BaseSkill, SkillMetadata, SkillCategory

        metadata = SkillMetadata(
            id=f"workflow:{wf.id}",
            name=wf.name,
            version="1.0.0",
            category=SkillCategory.COMPOSITE,
            description=wf.description,
        )

        composer = self

        class CompositeSkill(BaseSkill):
            def __init__(self):
                super().__init__(metadata)

            async def execute(self, params: dict, context: dict = None) -> dict:
                return await composer.execute_workflow(wf.id, params, context)

        return CompositeSkill()


def create_video_story_workflow() -> Workflow:
    return Workflow(
        id="video_story",
        name="视频故事工作流",
        description="生成一个完整的分镜视频故事（生成图片 → 理解图片 → 生成视频）",
        steps=[
            SkillStep(
                skill_id="image_generation",
                params={"prompt": "${story_prompt}", "style": "${style}", "size": "${size}"},
                description="生成故事插图",
                timeout=120.0,
            ),
            SkillStep(
                skill_id="image_understanding",
                params={"image_path": "${image_generation.image_path}", "question": "请描述这张图片的内容和风格"},
                description="理解生成的图片",
                timeout=60.0,
            ),
            SkillStep(
                skill_id="video_generation",
                params={"prompt": "${image_understanding.result}", "num_frames": "${num_frames}"},
                description="基于图片理解生成视频",
                timeout=300.0,
            ),
        ],
    )
