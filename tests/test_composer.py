import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_composer_cycle_detection():
    pytest.importorskip("skills.composer")
    from skills.composer import SkillComposer, Workflow, SkillStep, CyclicDependencyError

    composer = SkillComposer(registry=None)

    wf_a = Workflow(
        id="a", name="Workflow A", description="",
        steps=[SkillStep(skill_id="workflow:b")]
    )
    wf_b = Workflow(
        id="b", name="Workflow B", description="",
        steps=[SkillStep(skill_id="workflow:a")]
    )

    composer.register_workflow(wf_a)

    with pytest.raises(CyclicDependencyError):
        composer.register_workflow(wf_b)


@pytest.mark.asyncio
async def test_composer_workflow_execution():
    pytest.importorskip("skills.composer")
    from skills.composer import SkillComposer, Workflow, SkillStep

    registry = MagicMock()
    registry.get = MagicMock()

    skill = MagicMock()
    skill.execute = AsyncMock(return_value={"success": True, "outputs": {"result": "ok"}})
    registry.get.return_value = skill

    composer = SkillComposer(registry=registry)

    wf = Workflow(
        id="test_wf", name="Test", description="",
        steps=[
            SkillStep(skill_id="step1", params={"x": 1}, description="步骤1"),
            SkillStep(skill_id="step2", params={"y": 2}, description="步骤2"),
        ]
    )

    composer.register_workflow(wf)
    result = await composer.execute_workflow("test_wf", {})

    assert result["success"] is True


@pytest.mark.asyncio
async def test_composer_parallel_steps():
    pytest.importorskip("skills.composer")
    from skills.composer import SkillComposer, Workflow, SkillStep

    registry = MagicMock()
    skill = MagicMock()
    skill.execute = AsyncMock(return_value={"success": True, "outputs": {"result": "ok"}})
    registry.get.return_value = skill

    composer = SkillComposer(registry=registry)

    wf = Workflow(
        id="parallel_wf", name="Parallel", description="",
        steps=[
            SkillStep(skill_id="p1", parallel=True),
            SkillStep(skill_id="p2", parallel=True),
            SkillStep(skill_id="seq1", parallel=False),
        ]
    )

    composer.register_workflow(wf)
    result = await composer.execute_workflow("parallel_wf", {})

    assert result["success"] is True
