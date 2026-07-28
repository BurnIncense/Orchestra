import pytest
import tempfile
import yaml
from pathlib import Path


@pytest.mark.asyncio
async def test_permission_three_levels_allow_ask_deny():
    pytest.importorskip("mcp.client.permission_guard")
    from mcp.client.permission_guard import MCPPermissionGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "permissions.yaml"
        cfg_path.write_text(yaml.safe_dump({
            "permissions": {
                "default_policy": "ask",
                "servers": {
                    "filesystem": {
                        "read": "allow",
                        "write": "ask",
                        "delete": "deny",
                    },
                },
            },
        }), encoding="utf-8")

        guard = MCPPermissionGuard(str(cfg_path))

        policy, reason = guard.check_permission("filesystem", "read_file", "read")
        assert policy == "allow"

        policy, reason = guard.check_permission("filesystem", "write_file", "write")
        assert policy == "ask"

        policy, reason = guard.check_permission("filesystem", "delete_file", "delete")
        assert policy == "deny"


@pytest.mark.asyncio
async def test_permission_priority_tool_over_server_over_default():
    pytest.importorskip("mcp.client.permission_guard")
    from mcp.client.permission_guard import MCPPermissionGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "permissions.yaml"
        cfg_path.write_text(yaml.safe_dump({
            "permissions": {
                "default_policy": "allow",
                "servers": {
                    "filesystem": {
                        "call": "ask",
                    },
                },
                "tools": {
                    "filesystem:delete_file": {
                        "policy": "deny",
                    },
                },
            },
        }), encoding="utf-8")

        guard = MCPPermissionGuard(str(cfg_path))

        policy, reason = guard.check_permission("filesystem", "delete_file", "call")
        assert policy == "deny"
        assert "tool" in reason

        policy, reason = guard.check_permission("filesystem", "read_file", "call")
        assert policy == "ask"

        policy, reason = guard.check_permission("other_server", "some_tool", "call")
        assert policy == "allow"
