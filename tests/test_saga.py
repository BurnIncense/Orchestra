import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_saga_forward_execution():
    pytest.importorskip("core.saga")
    from core.saga import SagaEngine

    router = MagicMock()
    router.call_skill = AsyncMock(return_value={"success": True, "outputs": {}})

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SagaEngine(router, persistence_dir=tmpdir)

        steps = [
            {"skill_id": "step1", "params": {"x": 1}, "description": "步骤1"},
            {"skill_id": "step2", "params": {"y": 2}, "description": "步骤2"},
        ]

        result = await engine.execute("test_wf", steps)

        assert result["success"] is True
        assert "saga_id" in result
        assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_saga_compensation_reverse_order():
    pytest.importorskip("core.saga")
    from core.saga import SagaEngine, SagaStep, CompensationAction, CompensationType

    router = MagicMock()

    async def mock_call_skill(skill_id, params, context=None):
        if skill_id == "fail_step":
            return {"success": False, "error": "intentional failure"}
        return {"success": True, "outputs": {"image_path": "/tmp/test.png"}}

    router.call_skill = AsyncMock(side_effect=mock_call_skill)

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SagaEngine(router, persistence_dir=tmpdir)

        steps = [
            {"skill_id": "image_gen", "params": {"prompt": "test"}, "description": "生成图片"},
            {"skill_id": "fail_step", "params": {}, "description": "失败步骤"},
        ]

        result = await engine.execute("test_wf", steps)

        assert result["success"] is False
        assert result["compensated"] is True


@pytest.mark.asyncio
async def test_saga_wal_persistence():
    pytest.importorskip("core.saga")
    from core.saga import SagaEngine

    router = MagicMock()
    router.call_skill = AsyncMock(return_value={"success": True, "outputs": {}})

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SagaEngine(router, persistence_dir=tmpdir)

        steps = [
            {"skill_id": "step1", "params": {}, "description": "步骤1"},
        ]

        result = await engine.execute("test_wf", steps)

        saga_files = list(Path(tmpdir).glob("*.json"))
        assert len(saga_files) > 0

        for f in saga_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert "saga_id" in data
            assert "steps" in data


@pytest.mark.asyncio
async def test_saga_crash_recovery():
    pytest.importorskip("core.saga")
    from core.saga import SagaEngine, SagaState, SagaStep, CompensationAction, CompensationType

    router = MagicMock()
    router.call_skill = AsyncMock(return_value={"success": True, "outputs": {}})

    with tempfile.TemporaryDirectory() as tmpdir:
        crashed_state = SagaState(
            saga_id="crashed_001",
            workflow_id="test_wf",
            current_step=1,
            status="running",
            steps=[
                SagaStep(
                    id="step_0", description="步骤1", skill_id="s1",
                    params={}, status="completed", result={"success": True},
                    compensation=CompensationAction(
                        type=CompensationType.FILE_DELETE,
                        target="/tmp/fake.txt",
                        description="删除临时文件"
                    )
                ),
                SagaStep(
                    id="step_1", description="步骤2", skill_id="s2",
                    params={}, status="running"
                ),
            ],
        )

        state_path = Path(tmpdir) / "crashed_001.json"
        state_path.write_text(
            json.dumps(crashed_state.to_dict(), ensure_ascii=False),
            encoding="utf-8"
        )

        engine = SagaEngine(router, persistence_dir=tmpdir)
        assert engine.persistence_dir.exists()

        existing_files = list(Path(tmpdir).glob("*.json"))
        assert len(existing_files) >= 1
