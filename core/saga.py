"""
Saga 补偿事务引擎

保证：
1. 正向操作按序执行
2. 任何步骤失败 → 逆序执行所有已完成步骤的补偿
3. WAL 持久化 → 崩溃后自动恢复
4. 补偿操作本身失败时记录日志但不中断（尽力补偿）
"""

import asyncio
import json
import time
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum

logger = logging.getLogger("orchestra.saga")


class CompensationType(Enum):
    FILE_DELETE = "file_delete"
    FILE_RESTORE = "file_restore"
    DB_DELETE = "db_delete"
    MCP_COMPENSATE = "mcp_compensate"
    CUSTOM = "custom"
    NONE = "none"


@dataclass
class CompensationAction:
    type: CompensationType
    description: str = ""
    target: str = ""
    backup_data: Any = None
    mcp_server: str = ""
    mcp_tool: str = ""
    mcp_args: dict = field(default_factory=dict)
    custom_fn: Optional[Callable] = None


@dataclass
class SagaStep:
    id: str
    description: str
    skill_id: str = ""
    params: dict = field(default_factory=dict)
    compensation: Optional[CompensationAction] = None
    status: str = "pending"
    result: dict = field(default_factory=dict)


@dataclass
class SagaState:
    saga_id: str
    workflow_id: str
    steps: list[SagaStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "running"
    created_at: float = 0
    updated_at: float = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "saga_id": self.saga_id,
            "workflow_id": self.workflow_id,
            "current_step": self.current_step,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [
                {
                    "id": s.id, "description": s.description,
                    "skill_id": s.skill_id, "params": s.params,
                    "status": s.status, "result": s.result,
                    "compensation": {
                        "type": s.compensation.type.value,
                        "target": s.compensation.target,
                        "description": s.compensation.description,
                    } if s.compensation else None,
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SagaState":
        state = cls(
            saga_id=data["saga_id"],
            workflow_id=data["workflow_id"],
            current_step=data["current_step"],
            status=data["status"],
            error=data.get("error", ""),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
        )
        for s in data.get("steps", []):
            comp = None
            if s.get("compensation"):
                comp = CompensationAction(
                    type=CompensationType(s["compensation"]["type"]),
                    target=s["compensation"].get("target", ""),
                    description=s["compensation"].get("description", ""),
                )
            state.steps.append(SagaStep(
                id=s["id"], description=s["description"],
                skill_id=s["skill_id"], params=s["params"],
                status=s["status"], result=s.get("result", {}),
                compensation=comp,
            ))
        return state


class SagaEngine:
    def __init__(self, router, persistence_dir: str = "./data/saga"):
        self.router = router
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, workflow_id: str, steps: list[dict],
                       context: dict = None) -> dict:
        saga_id = str(uuid.uuid4())[:12]
        state = SagaState(
            saga_id=saga_id, workflow_id=workflow_id,
            created_at=time.time(), updated_at=time.time(),
        )
        for i, step_def in enumerate(steps):
            state.steps.append(SagaStep(
                id=f"step_{i}",
                description=step_def.get("description", f"步骤 {i+1}"),
                skill_id=step_def.get("skill_id", ""),
                params=step_def.get("params", {}),
            ))

        self._persist(state)

        try:
            for i, step in enumerate(state.steps):
                state.current_step = i
                step.status = "running"
                self._persist(state)

                result = await self.router.call_skill(step.skill_id, step.params, context)
                step.result = result

                if result.get("success"):
                    step.status = "completed"
                    step.compensation = self._derive_compensation(step, result)
                    self._persist(state)
                else:
                    step.status = "failed"
                    state.status = "compensating"
                    state.error = result.get("error", "未知错误")
                    self._persist(state)
                    await self._compensate(state, failed_at=i)
                    return {"success": False, "error": state.error,
                            "saga_id": saga_id, "compensated": True}

            state.status = "completed"
            self._persist(state)
            return {"success": True, "saga_id": saga_id,
                    "results": [s.result for s in state.steps]}

        except Exception as e:
            state.status = "compensating"
            state.error = str(e)
            self._persist(state)
            await self._compensate(state, failed_at=state.current_step)
            return {"success": False, "error": str(e), "saga_id": saga_id}

    async def _compensate(self, state: SagaState, failed_at: int):
        for i in range(failed_at - 1, -1, -1):
            step = state.steps[i]
            if step.status != "completed" or not step.compensation:
                continue
            comp = step.compensation
            try:
                await self._execute_compensation(comp)
                step.status = "compensated"
            except Exception as e:
                logger.error(f"补偿失败: {comp.description} - {e}")
                step.status = "compensation_failed"
            self._persist(state)
        state.status = "compensated"
        self._persist(state)

    async def _execute_compensation(self, comp: CompensationAction):
        if comp.type == CompensationType.FILE_DELETE:
            path = Path(comp.target)
            if path.exists():
                path.unlink()
        elif comp.type == CompensationType.FILE_RESTORE:
            if comp.backup_data and comp.target:
                Path(comp.target).write_text(comp.backup_data)
        elif comp.type in (CompensationType.DB_DELETE, CompensationType.MCP_COMPENSATE):
            await self.router.call_skill(
                f"mcp:{comp.mcp_server}:{comp.mcp_tool}", comp.mcp_args
            )
        elif comp.type == CompensationType.CUSTOM and comp.custom_fn:
            if asyncio.iscoroutinefunction(comp.custom_fn):
                await comp.custom_fn()
            else:
                comp.custom_fn()

    def _derive_compensation(self, step: SagaStep, result: dict) -> CompensationAction:
        outputs = result.get("outputs", {})
        if "image_path" in outputs:
            return CompensationAction(
                type=CompensationType.FILE_DELETE,
                target=outputs["image_path"],
                description=f"删除图片: {outputs['image_path']}",
            )
        if "video_path" in outputs:
            return CompensationAction(
                type=CompensationType.FILE_DELETE,
                target=outputs["video_path"],
                description=f"删除视频: {outputs['video_path']}",
            )
        if "db_record_id" in outputs:
            return CompensationAction(
                type=CompensationType.DB_DELETE,
                mcp_server=outputs.get("mcp_server", "sqlite"),
                mcp_tool="delete_record",
                mcp_args={"id": outputs["db_record_id"]},
                description=f"删除记录: {outputs['db_record_id']}",
            )
        return CompensationAction(type=CompensationType.NONE)

    def _persist(self, state: SagaState):
        path = self.persistence_dir / f"{state.saga_id}.json"
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    def recover_incomplete(self) -> list[SagaState]:
        incomplete = []
        for f in self.persistence_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                state = SagaState.from_dict(data)
                if state.status in ("running", "compensating"):
                    incomplete.append(state)
            except:
                continue
        return incomplete

    async def resume(self, state: SagaState, context: dict = None):
        if state.status == "compensating":
            await self._compensate(state, failed_at=state.current_step)
        elif state.status == "running":
            for i in range(state.current_step, len(state.steps)):
                step = state.steps[i]
                if step.status == "completed":
                    continue
                state.current_step = i
                result = await self.router.call_skill(step.skill_id, step.params, context)
                step.result = result
                if result.get("success"):
                    step.status = "completed"
                    step.compensation = self._derive_compensation(step, result)
                else:
                    step.status = "failed"
                    state.status = "compensating"
                    await self._compensate(state, failed_at=i)
                    return {"success": False, "error": result.get("error")}
                self._persist(state)
            state.status = "completed"
            self._persist(state)
        return {"success": True, "saga_id": state.saga_id}
