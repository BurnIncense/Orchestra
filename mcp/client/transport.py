"""
MCP 传输层 — 支持 stdio 子进程 和 SSE HTTP 两种通信方式
所有外部依赖均采用延迟导入，mcp 包未安装时也可 import
"""

import asyncio
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("orchestra.mcp.transport")


class BaseTransport(ABC):
    """传输层抽象基类"""

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def send_message(self, message: dict) -> None:
        ...

    @abstractmethod
    async def receive_message(self) -> Optional[dict]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class StdioTransport(BaseTransport):
    """通过子进程 stdio 通信的传输层"""

    def __init__(self, command: str, args: list = None, env: dict = None,
                 cwd: str = None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd
        self._process: Optional[asyncio.subprocess.Process] = None
        self._stdin_lock = asyncio.Lock()
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return

        merged_env = os.environ.copy()
        merged_env.update(self.env)

        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
            cwd=self.cwd or Path.cwd(),
        )
        self._connected = True
        logger.debug(f"StdioTransport 已启动: {self.command} {' '.join(self.args)}")

    async def send_message(self, message: dict) -> None:
        if not self._connected or self._process is None:
            raise RuntimeError("StdioTransport 未连接")

        payload = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._stdin_lock:
            self._process.stdin.write(payload)
            await self._process.stdin.drain()

    async def receive_message(self) -> Optional[dict]:
        if not self._connected or self._process is None:
            return None

        try:
            line = await self._process.stdout.readline()
            if not line:
                return None
            text = line.decode("utf-8").strip()
            if not text:
                return None
            return json.loads(text)
        except (json.JSONDecodeError, asyncio.CancelledError):
            return None

    async def close(self) -> None:
        if not self._connected:
            return
        self._connected = False

        if self._process is not None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                try:
                    self._process.kill()
                    await self._process.wait()
                except Exception:
                    pass
            self._process = None
        logger.debug("StdioTransport 已关闭")


class SSETransport(BaseTransport):
    """通过 SSE HTTP 通信的传输层"""

    def __init__(self, url: str, headers: dict = None, ssl_context=None):
        self.url = url
        self.headers = headers or {}
        self.ssl_context = ssl_context
        self._session = None
        self._response = None
        self._event_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return

        try:
            import httpx
        except ImportError:
            httpx = None

        if httpx is None:
            raise RuntimeError("httpx 未安装，无法使用 SSETransport")

        self._session = httpx.AsyncClient(
            headers=self.headers,
            verify=self.ssl_context if self.ssl_context is not None else True,
            timeout=httpx.Timeout(connect=10.0, read=None, write=30.0),
        )

        self._response = await self._session.send(
            self._session.build_request("GET", self.url),
            stream=True,
        )
        self._response.raise_for_status()

        self._connected = True
        self._reader_task = asyncio.create_task(self._read_sse_events())
        logger.debug(f"SSETransport 已连接: {self.url}")

    async def _read_sse_events(self) -> None:
        try:
            buffer = ""
            async for chunk in self._response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)
                    message = self._parse_sse_event(event_text)
                    if message is not None:
                        await self._event_queue.put(message)
        except Exception as e:
            logger.debug(f"SSE 读取循环结束: {e}")
        finally:
            await self._event_queue.put(None)

    @staticmethod
    def _parse_sse_event(event_text: str) -> Optional[dict]:
        data_lines = []
        for line in event_text.split("\n"):
            if line.startswith("data: "):
                data_lines.append(line[6:])
            elif line.startswith("data:"):
                data_lines.append(line[5:])
        if not data_lines:
            return None
        data_str = "\n".join(data_lines)
        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            return None

    async def send_message(self, message: dict) -> None:
        if not self._connected or self._session is None:
            raise RuntimeError("SSETransport 未连接")

        post_url = self.url.rsplit("/", 1)[0] + "/messages"
        response = await self._session.post(post_url, json=message)
        response.raise_for_status()

    async def receive_message(self) -> Optional[dict]:
        if not self._connected:
            return None
        return await self._event_queue.get()

    async def close(self) -> None:
        if not self._connected:
            return
        self._connected = False

        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None

        if self._response is not None:
            try:
                await self._response.aclose()
            except Exception:
                pass
            self._response = None

        if self._session is not None:
            try:
                await self._session.aclose()
            except Exception:
                pass
            self._session = None

        logger.debug("SSETransport 已关闭")
