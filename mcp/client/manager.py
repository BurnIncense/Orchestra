"""
MCP 客户端管理器 — 连接管理、工具发现、调用、配额与健康检查
所有外部依赖均采用延迟导入，mcp 包未安装时也可 import
"""

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("orchestra.mcp.client")


class _ServerQuota:
    """Per-Server 调用配额与健康状态"""

    def __init__(self, max_concurrent: int = 3, rate_limit_per_min: int = 60):
        self.max_concurrent = max_concurrent
        self.rate_limit_per_min = rate_limit_per_min
        self.current_concurrent = 0
        self.call_timestamps: list[float] = []
        self.last_health_check = 0.0
        self.is_healthy = True
        self.consecutive_failures = 0
        self.total_calls = 0
        self.total_failures = 0
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def check_rate_limit(self) -> bool:
        now = time.time()
        self.call_timestamps = [t for t in self.call_timestamps if now - t < 60]
        return len(self.call_timestamps) < self.rate_limit_per_min

    def record_call(self, success: bool):
        self.total_calls += 1
        self.call_timestamps.append(time.time())
        if not success:
            self.total_failures += 1
            self.consecutive_failures += 1
            if self.consecutive_failures >= 5:
                self.is_healthy = False
        else:
            self.consecutive_failures = 0
            self.is_healthy = True


class MCPClientManager:
    """MCP 客户端管理器"""

    def __init__(self, config_path: str = "./mcp/config/servers.yaml"):
        self.config_path = Path(config_path)
        self.connections: dict[str, Any] = {}
        self.discovered_tools: dict[str, list] = {}
        self._server_configs: dict = {}
        self._quotas: dict[str, _ServerQuota] = {}
        self._connect_lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._retry_config = {
            "max_retries": 3,
            "base_delay": 1.0,
            "backoff_factor": 2.0,
        }
        self._load_config()

    def _load_config(self) -> None:
        try:
            import yaml
        except ImportError:
            yaml = None

        if yaml is None:
            logger.warning("pyyaml 未安装，无法加载 MCP 服务器配置")
            return

        if not self.config_path.exists():
            logger.debug(f"MCP 配置文件不存在: {self.config_path}")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = f.read()

            raw = re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(
                m.group(1).split(":-")[0],
                m.group(1).split(":-")[1] if ":-" in m.group(1) else ""
            ), raw)

            data = yaml.safe_load(raw) or {}
            self._server_configs = data.get("mcp_servers", {}) or {}
            logger.info(f"已加载 {len(self._server_configs)} 个 MCP 服务器配置")
        except Exception as e:
            logger.warning(f"加载 MCP 配置失败: {e}")

    async def connect_all(self) -> None:
        async with self._connect_lock:
            logger.info("连接 MCP 服务器...")

            tasks = []
            for server_name, cfg in self._server_configs.items():
                if not cfg.get("enabled", False):
                    continue
                tasks.append(self._connect_server(server_name, cfg))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self._start_health_check()
            logger.info(f"MCP 连接完成: {len(self.connections)} 个服务器已连接")

    async def _connect_server(self, server_name: str, cfg: dict) -> None:
        try:
            session = await self._try_connect_with_retry(server_name, cfg)
            if session is not None:
                self.connections[server_name] = session
                self._quotas[server_name] = _ServerQuota(
                    max_concurrent=cfg.get("max_concurrent", 3),
                    rate_limit_per_min=cfg.get("rate_limit", 60),
                )
                tools = await self._discover_tools(server_name, session)
                self.discovered_tools[server_name] = tools
                logger.info(f"MCP 服务器 [{server_name}] 已连接，发现 {len(tools)} 个工具")
        except Exception as e:
            logger.error(f"连接 MCP 服务器 [{server_name}] 失败: {e}")

    async def _try_connect_with_retry(self, server_name: str, cfg: dict) -> Optional[Any]:
        transport_type = cfg.get("transport", "stdio")
        last_error = None

        for attempt in range(self._retry_config["max_retries"]):
            try:
                if transport_type == "stdio":
                    return await self._connect_stdio(server_name, cfg)
                elif transport_type == "sse":
                    return await self._connect_sse(server_name, cfg)
                else:
                    logger.warning(f"未知传输类型: {transport_type}")
                    return None
            except Exception as e:
                last_error = e
                delay = self._retry_config["base_delay"] * (
                    self._retry_config["backoff_factor"] ** attempt
                )
                logger.debug(
                    f"连接 [{server_name}] 第 {attempt + 1} 次失败，"
                    f"{delay:.1f}s 后重试: {e}"
                )
                await asyncio.sleep(delay)

        logger.error(f"连接 [{server_name}] 重试耗尽: {last_error}")
        return None

    async def _connect_stdio(self, server_name: str, cfg: dict) -> Any:
        try:
            from mcp import ClientSession
        except ImportError:
            ClientSession = None

        if ClientSession is None:
            raise RuntimeError("mcp 包未安装，无法建立 stdio 连接")

        from mcp.client.transport import stdio_client

        command = cfg["command"]
        args = list(cfg.get("args", []))
        env = cfg.get("env", {}) or {}

        merged_env = os.environ.copy()
        for k, v in env.items():
            merged_env[k] = os.path.expandvars(v) if isinstance(v, str) else v

        async with stdio_client(command, *args, env=merged_env) as (read_stream, write_stream):
            session = ClientSession(read_stream, write_stream)
            await session.initialize()
            return session

    async def _connect_sse(self, server_name: str, cfg: dict) -> Any:
        try:
            from mcp import ClientSession
        except ImportError:
            ClientSession = None

        if ClientSession is None:
            raise RuntimeError("mcp 包未安装，无法建立 SSE 连接")

        from mcp.client.sse import sse_client

        url = cfg.get("url", "")
        if not url:
            host = cfg.get("host", "localhost")
            port = cfg.get("port", 9100)
            url = f"http://{host}:{port}/mcp"

        ssl_context = None
        if cfg.get("tls", {}).get("enabled", False):
            import ssl
            ssl_context = ssl.create_default_context()
            if cfg["tls"].get("allow_self_signed", False):
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        async with sse_client(url, ssl_context=ssl_context) as (read_stream, write_stream):
            session = ClientSession(read_stream, write_stream)
            await session.initialize()
            return session

    async def _discover_tools(self, server_name: str, session: Any) -> list:
        try:
            result = await session.list_tools()
            tools = getattr(result, "tools", []) or []
            return list(tools)
        except Exception as e:
            logger.warning(f"发现 [{server_name}] 工具失败: {e}")
            return []

    def _start_health_check(self) -> None:
        if self._health_check_task is not None and not self._health_check_task.done():
            return
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                await self._run_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"健康检查循环异常: {e}")

    async def _run_health_check(self) -> None:
        for server_name, session in list(self.connections.items()):
            quota = self._quotas.get(server_name)
            if quota is None:
                continue
            quota.last_health_check = time.time()
            try:
                await session.list_tools()
                quota.is_healthy = True
                quota.consecutive_failures = 0
            except Exception as e:
                quota.is_healthy = False
                logger.debug(f"[{server_name}] 健康检查失败: {e}")

    async def disconnect_all(self) -> None:
        logger.info("断开 MCP 服务器连接...")

        if self._health_check_task is not None and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except (asyncio.CancelledError, Exception):
                pass
            self._health_check_task = None

        for server_name, session in list(self.connections.items()):
            try:
                if hasattr(session, "close"):
                    await session.close()
            except Exception as e:
                logger.debug(f"关闭 [{server_name}] 会话失败: {e}")

        self.connections.clear()
        self.discovered_tools.clear()
        self._quotas.clear()
        logger.info("所有 MCP 连接已断开")

    async def call_tool(self, server_name: str, tool_name: str, args: dict) -> dict:
        logger.debug(f"调用 MCP 工具: {server_name}.{tool_name}")

        if server_name not in self.connections:
            return {"success": False, "error": f"MCP 服务器未连接: {server_name}"}

        quota = self._quotas.get(server_name)
        if quota is not None and not quota.is_healthy:
            return {"success": False, "error": f"MCP 服务器不健康: {server_name}"}

        if quota is not None and not quota.check_rate_limit():
            return {"success": False, "error": f"[{server_name}] 超过速率限制"}

        session = self.connections[server_name]

        if quota is not None:
            await quota._semaphore.acquire()
            quota.current_concurrent += 1

        try:
            result = await self._call_with_retry(session, tool_name, args)
            if quota is not None:
                quota.record_call(success=True)
            return {"success": True, "outputs": {"result": result}}
        except Exception as e:
            if quota is not None:
                quota.record_call(success=False)
            return {"success": False, "error": str(e)}
        finally:
            if quota is not None:
                quota.current_concurrent -= 1
                quota._semaphore.release()

    async def _call_with_retry(self, session: Any, tool_name: str, args: dict) -> Any:
        last_error = None
        for attempt in range(self._retry_config["max_retries"]):
            try:
                result = await session.call_tool(tool_name, args)
                return result
            except Exception as e:
                last_error = e
                if attempt < self._retry_config["max_retries"] - 1:
                    delay = self._retry_config["base_delay"] * (
                        self._retry_config["backoff_factor"] ** attempt
                    )
                    await asyncio.sleep(delay)
        raise last_error

    def status(self) -> dict:
        result = {
            "connected_servers": len(self.connections),
            "servers": {},
        }
        for server_name in self.connections:
            quota = self._quotas.get(server_name)
            tools = self.discovered_tools.get(server_name, [])
            result["servers"][server_name] = {
                "connected": True,
                "tool_count": len(tools),
                "tools": [getattr(t, "name", str(t)) for t in tools],
                "healthy": quota.is_healthy if quota else None,
                "total_calls": quota.total_calls if quota else 0,
                "total_failures": quota.total_failures if quota else 0,
                "current_concurrent": quota.current_concurrent if quota else 0,
            }
        for server_name, cfg in self._server_configs.items():
            if server_name not in result["servers"]:
                result["servers"][server_name] = {
                    "connected": False,
                    "enabled": cfg.get("enabled", False),
                }
        return result
