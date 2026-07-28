"""
MCP 权限守卫 — 基于策略的权限检查
所有外部依赖均采用延迟导入，mcp 包未安装时也可 import
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("orchestra.mcp.permission")

_VALID_POLICIES = {"allow", "ask", "deny"}


class MCPPermissionGuard:
    """MCP 权限守卫"""

    def __init__(self, config_path: str = "./mcp/config/permissions.yaml"):
        self.config_path = Path(config_path)
        self.default_policy: str = "ask"
        self.server_policies: dict = {}
        self.tool_policies: dict = {}
        self._load_config()

    def _load_config(self) -> None:
        try:
            import yaml
        except ImportError:
            yaml = None

        if yaml is None:
            logger.debug("pyyaml 未安装，使用默认权限策略")
            return

        if not self.config_path.exists():
            logger.debug(f"权限配置文件不存在: {self.config_path}，使用默认策略")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = f.read()

            raw = re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(
                m.group(1).split(":-")[0],
                m.group(1).split(":-")[1] if ":-" in m.group(1) else ""
            ), raw)

            data = yaml.safe_load(raw) or {}
            perm_cfg = data.get("permissions", {}) or {}

            default = perm_cfg.get("default_policy", "ask")
            if default in _VALID_POLICIES:
                self.default_policy = default

            self.server_policies = perm_cfg.get("servers", {}) or {}
            self.tool_policies = perm_cfg.get("tools", {}) or {}

            logger.info(
                f"权限配置已加载: default={self.default_policy}, "
                f"servers={len(self.server_policies)}, tools={len(self.tool_policies)}"
            )
        except Exception as e:
            logger.warning(f"加载权限配置失败: {e}，使用默认策略")

    def check_permission(
        self, server_name: str, tool_name: str, action: str = "call"
    ) -> tuple[str, str]:
        """
        检查调用权限

        Returns:
            (policy, reason) — policy ∈ {"allow", "ask", "deny"}
            优先级：tool_policy > server_policy > default_policy
        """
        tool_key = f"{server_name}:{tool_name}"

        if tool_key in self.tool_policies:
            tool_cfg = self.tool_policies[tool_key]
            if isinstance(tool_cfg, dict):
                policy = tool_cfg.get("policy", self.default_policy)
            else:
                policy = tool_cfg
            if policy in _VALID_POLICIES:
                return policy, f"tool 策略: {tool_key}"

        if tool_name in self.tool_policies:
            tool_cfg = self.tool_policies[tool_name]
            if isinstance(tool_cfg, dict):
                policy = tool_cfg.get("policy", self.default_policy)
            else:
                policy = tool_cfg
            if policy in _VALID_POLICIES:
                return policy, f"tool 策略: {tool_name}"

        if server_name in self.server_policies:
            server_cfg = self.server_policies[server_name]
            if isinstance(server_cfg, dict):
                if action in server_cfg:
                    policy = server_cfg[action]
                    if policy in _VALID_POLICIES:
                        return policy, f"server 策略: {server_name}.{action}"
                if "*" in server_cfg:
                    policy = server_cfg["*"]
                    if policy in _VALID_POLICIES:
                        return policy, f"server 策略: {server_name}.*"

        return self.default_policy, f"默认策略: {self.default_policy}"
