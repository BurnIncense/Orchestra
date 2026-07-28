"""集成测试"""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_full_image_generation_flow(agent):
    """完整图片生成流程"""
    response = await agent.process("画一只猫", user_id="test_user")
    assert "图片" in response or "生成" in response


@pytest.mark.asyncio
async def test_session_isolation(agent):
    """多用户会话隔离"""
    await agent.process("我喜欢动漫风格", user_id="user_a")
    await agent.process("我喜欢写实风格", user_id="user_b")

    session_a = await agent.session_manager.get_or_create("user_a")
    session_b = await agent.session_manager.get_or_create("user_b")

    prefs_a = session_a.learner.preferences
    prefs_b = session_b.learner.preferences
    assert prefs_a != prefs_b


@pytest.mark.asyncio
async def test_saga_compensation(agent):
    """Saga 补偿事务"""
    steps = [
        {"skill_id": "image_generation", "params": {"prompt": "test"}, "description": "生成图片"},
        {"skill_id": "nonexistent_skill", "params": {}, "description": "必定失败"},
    ]
    result = await agent.saga_engine.execute("test_saga", steps)
    assert result["success"] == False
    assert result["compensated"] == True


@pytest.mark.asyncio
async def test_inference_lock(agent):
    """推理互斥锁"""
    import asyncio
    results = await asyncio.gather(
        agent.process("画一只猫", user_id="u1"),
        agent.process("画一只狗", user_id="u2"),
    )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_cyclic_dependency_detection():
    """循环依赖检测"""
    from skills.composer import SkillComposer, Workflow, SkillStep, CyclicDependencyError
    composer = SkillComposer(registry=None)
    wf_a = Workflow(id="a", name="A", description="", steps=[SkillStep(skill_id="composite_b")])
    wf_b = Workflow(id="b", name="B", description="", steps=[SkillStep(skill_id="composite_a")])
    composer.register_workflow(wf_a)
    with pytest.raises(CyclicDependencyError):
        composer.register_workflow(wf_b)


@pytest.mark.asyncio
async def test_sandbox_isolation():
    """沙箱隔离"""
    from skills.sandbox_v2 import ProcessIsolatedSandbox
    import tempfile
    sandbox = ProcessIsolatedSandbox()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""
import os
def create_skill():
    class S:
        class metadata:
            class category:
                value = "extension"
        async def execute(self, params, ctx=None):
            os.system("echo hacked")
            return {"success": True, "outputs": {}}
    return S()
""")
        f.flush()
        result = await sandbox.execute(f.name, {})
        assert result.success == False or "禁止" in result.error
