"""
MCP 资源管理 — 用户级 ACL
"""

import logging
from fnmatch import fnmatch

logger = logging.getLogger("orchestra.mcp.resources")


class ResourceManager:
    """资源管理器（基于 URI 模式的 ACL）"""

    def __init__(self):
        self.acl: dict = {
            "orchestra://users/*": "owner_only",
            "orchestra://shared/*": "authenticated",
        }

    def _match_pattern(self, resource_uri: str, pattern: str) -> bool:
        return fnmatch(resource_uri, pattern)

    def _get_access_level(self, resource_uri: str) -> str:
        for pattern, level in self.acl.items():
            if self._match_pattern(resource_uri, pattern):
                return level
        return "authenticated"

    def check_access(
        self, resource_uri: str, user_id: str, auth_level: str
    ) -> bool:
        """
        检查用户是否有权访问资源

        Args:
            resource_uri: 资源 URI，如 orchestra://users/user_a/images/foo.png
            user_id: 用户 ID
            auth_level: 认证级别 ∈ {"owner", "authenticated", "anonymous"}

        Returns:
            True 表示允许访问
        """
        required_level = self._get_access_level(resource_uri)

        if required_level == "owner_only":
            if auth_level != "owner":
                return False
            if not resource_uri.startswith(f"orchestra://users/{user_id}/"):
                return False
            return True

        if required_level == "authenticated":
            return auth_level in {"owner", "authenticated"}

        if required_level == "public":
            return True

        return auth_level in {"owner", "authenticated"}

    def add_acl_rule(self, pattern: str, access_level: str) -> None:
        """添加 ACL 规则"""
        self.acl[pattern] = access_level
        logger.debug(f"已添加 ACL 规则: {pattern} -> {access_level}")

    def remove_acl_rule(self, pattern: str) -> None:
        """移除 ACL 规则"""
        if pattern in self.acl:
            del self.acl[pattern]
            logger.debug(f"已移除 ACL 规则: {pattern}")
