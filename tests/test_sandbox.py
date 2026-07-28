import pytest
import tempfile
import sys


@pytest.mark.asyncio
async def test_sandbox_os_system_forbidden():
    pytest.importorskip("skills.sandbox_v2")
    from skills.sandbox_v2 import ProcessIsolatedSandbox, SandboxConfig

    config = SandboxConfig(allow_subprocess=False, allow_network=False)
    sandbox = ProcessIsolatedSandbox(config)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
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
        skill_path = f.name

    result = await sandbox.execute(skill_path, {})

    assert result.success is False or ("禁止" in result.error)


@pytest.mark.asyncio
async def test_sandbox_timeout():
    pytest.importorskip("skills.sandbox_v2")
    from skills.sandbox_v2 import ProcessIsolatedSandbox, SandboxConfig

    config = SandboxConfig(max_cpu_seconds=1)
    sandbox = ProcessIsolatedSandbox(config)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("""
import time
def create_skill():
    class S:
        class metadata:
            class category:
                value = "extension"
        async def execute(self, params, ctx=None):
            time.sleep(10)
            return {"success": True, "outputs": {}}
    return S()
""")
        f.flush()
        skill_path = f.name

    result = await sandbox.execute(skill_path, {})
    assert result.success is False


@pytest.mark.asyncio
async def test_sandbox_windows_fallback():
    if sys.platform != "win32":
        pytest.skip("仅在 Windows 平台测试降级")

    pytest.importorskip("skills.sandbox_v2")
    from skills.sandbox_v2 import ProcessIsolatedSandbox, SandboxConfig

    config = SandboxConfig(allow_network=True, allow_subprocess=True)
    sandbox = ProcessIsolatedSandbox(config)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("""
def create_skill():
    class S:
        class metadata:
            class category:
                value = "extension"
        async def execute(self, params, ctx=None):
            return {"success": True, "outputs": {"result": "ok"}}
    return S()
""")
        f.flush()
        skill_path = f.name

    result = await sandbox.execute(skill_path, {})
    assert result.success is True
    assert result.output.get("result") == "ok"
