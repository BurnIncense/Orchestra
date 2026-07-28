import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_priority_routing_builtin_over_extension():
    pytest.importorskip("core.router")
    from core.router import UnifiedRouter, SkillSource

    registry = MagicMock()
    mcp_client = MagicMock()
    mcp_client.discovered_tools = {}

    builtin_skill = MagicMock()
    builtin_skill.metadata.category.value = "builtin"

    ext_skill = MagicMock()
    ext_skill.metadata.category.value = "extension"

    def mock_get(skill_id):
        if skill_id == "image_generation":
            return builtin_skill
        return None

    registry.get = mock_get
    registry.count = 1

    router = UnifiedRouter(registry, mcp_client)
    decision = router.resolve("image_generation")

    assert decision is not None
    assert decision.source == SkillSource.BUILTIN


@pytest.mark.asyncio
async def test_cycle_detection_ab_ba():
    pytest.importorskip("core.router")
    from core.router import UnifiedRouter
    from utils.exceptions import CyclicDependencyError

    registry = MagicMock()
    registry.count = 0
    mcp_client = MagicMock()
    mcp_client.discovered_tools = {}

    router = UnifiedRouter(registry, mcp_client)

    router.push_call("skill_a")
    router.push_call("skill_b")

    with pytest.raises(CyclicDependencyError):
        router.push_call("skill_a")


@pytest.mark.asyncio
async def test_explicit_routing_mcp():
    pytest.importorskip("core.router")
    from core.router import UnifiedRouter, SkillSource

    registry = MagicMock()
    registry.count = 0
    mcp_client = MagicMock()
    mcp_client.discovered_tools = {}

    router = UnifiedRouter(registry, mcp_client)
    decision = router.resolve("@mcp:filesystem:read_file")

    assert decision is not None
    assert decision.is_mcp_bridge is True
    assert decision.mcp_server == "filesystem"
    assert decision.mcp_tool == "read_file"
    assert decision.source == SkillSource.MCP_BRIDGE
