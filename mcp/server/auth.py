"""
MCP 认证 — API Key 验证与速率限制
"""

import logging
import time
from typing import Any, Optional

logger = logging.getLogger("orchestra.mcp.auth")


class MCPAuthenticator:
    """MCP 认证器"""

    def __init__(self, api_keys_config: list = None):
        self.api_keys: dict[str, dict] = {}
        self._rate_limits: dict[str, list[float]] = {}

        if api_keys_config:
            for key_cfg in api_keys_config:
                key_value = key_cfg.get("key", "")
                if key_value:
                    self.api_keys[key_value] = {
                        "name": key_cfg.get("name", "unknown"),
                        "permissions": key_cfg.get("permissions", ["*"]),
                        "rate_limit": key_cfg.get("rate_limit", 60),
                    }

    def validate_key(self, api_key: str) -> tuple[bool, dict]:
        """
        验证 API Key

        Returns:
            (valid, key_info)
        """
        if not api_key:
            return False, {}

        if api_key not in self.api_keys:
            logger.debug(f"无效的 API Key: {api_key[:8]}...")
            return False, {}

        key_info = self.api_keys[api_key]
        logger.debug(f"API Key 验证通过: {key_info.get('name')}")
        return True, key_info

    def check_rate_limit(self, api_key: str) -> bool:
        """
        检查是否超过速率限制（默认 60次/分钟）

        Returns:
            True 表示可以继续调用，False 表示超过限制
        """
        if not api_key or api_key not in self.api_keys:
            return False

        key_info = self.api_keys[api_key]
        limit = key_info.get("rate_limit", 60)

        now = time.time()
        timestamps = self._rate_limits.setdefault(api_key, [])
        timestamps[:] = [t for t in timestamps if now - t < 60]

        if len(timestamps) >= limit:
            logger.debug(
                f"[{key_info.get('name')}] 超过速率限制: "
                f"{len(timestamps)}/{limit}/min"
            )
            return False

        timestamps.append(now)
        return True

    def has_permission(self, api_key: str, permission: str) -> bool:
        """检查 API Key 是否有指定权限"""
        if api_key not in self.api_keys:
            return False

        perms = self.api_keys[api_key].get("permissions", [])
        if "*" in perms:
            return True
        return permission in perms
