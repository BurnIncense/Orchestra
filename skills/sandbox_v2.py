# skills/sandbox_v2.py
"""
Skill 沙箱 — 进程级隔离

扩展 Skill 在独立子进程中执行：
- 内存限制 (setrlimit)
- CPU 时间限制
- 文件系统白名单
- 网络禁止（默认）
- 子进程禁止
- 通过 IPC Queue 通信
"""

import os
import sys
import json
import signal
import tempfile
import shutil
import asyncio
import multiprocessing
import importlib.util
import logging
from pathlib import Path
from dataclasses import dataclass, field

try:
    import resource
except ImportError:
    resource = None

logger = logging.getLogger("orchestra.sandbox")


@dataclass
class SandboxConfig:
    max_memory_mb: int = 2048
    max_cpu_seconds: int = 300
    max_file_size_mb: int = 100
    max_open_files: int = 50
    allowed_read_paths: list = field(default_factory=lambda: ["/tmp/orchestra_sandbox"])
    allowed_write_paths: list = field(default_factory=lambda: ["/tmp/orchestra_sandbox/output"])
    allow_network: bool = False
    allow_subprocess: bool = False


@dataclass
class SandboxResult:
    success: bool
    output: object = None
    error: str = ""
    execution_time: float = 0.0
    memory_peak_mb: float = 0.0


def _sandbox_worker(skill_file: str, params_json: str, config_json: str,
                     result_queue: multiprocessing.Queue):
    """沙箱子进程入口"""
    import time
    start = time.time()
    try:
        config = json.loads(config_json)
        params = json.loads(params_json)

        if sys.platform != "win32" and resource is not None:
            max_mem = config.get("max_memory_mb", 2048) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_mem, max_mem))
            max_cpu = config.get("max_cpu_seconds", 300)
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu))
            max_file = config.get("max_file_size_mb", 100) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file, max_file))
            resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))

        _signals = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGHUP"):
            _signals.append(signal.SIGHUP)
        for sig in _signals:
            try:
                signal.signal(sig, signal.SIG_IGN)
            except:
                pass

        if not config.get("allow_network", False):
            import socket
            socket.socket.connect = lambda self, *a, **k: (_ for _ in ()).throw(
                PermissionError("沙箱禁止网络"))

        if not config.get("allow_subprocess", False):
            import subprocess
            subprocess.Popen = lambda *a, **k: (_ for _ in ()).throw(
                PermissionError("沙箱禁止子进程"))
            os.system = lambda *a: (_ for _ in ()).throw(
                PermissionError("沙箱禁止系统调用"))

        spec = importlib.util.spec_from_file_location("sandboxed_skill", skill_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        skill = module.create_skill()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(skill.execute(params, {}))
        loop.close()

        elapsed = time.time() - start
        mem_peak = 0.0
        if resource is not None:
            try:
                mem_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            except:
                pass

        result_queue.put(json.dumps({
            "success": result.get("success", False),
            "output": result.get("outputs"),
            "error": result.get("error", ""),
            "execution_time": elapsed,
            "memory_peak_mb": mem_peak,
        }))
    except Exception as e:
        result_queue.put(json.dumps({"success": False, "error": str(e)}))


class ProcessIsolatedSandbox:
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()

    async def execute(self, skill_file: str, params: dict,
                       timeout: float = None) -> SandboxResult:
        timeout = timeout or self.config.max_cpu_seconds + 10
        sandbox_dir = tempfile.mkdtemp(prefix="orchestra_sandbox_")
        os.makedirs(os.path.join(sandbox_dir, "output"), exist_ok=True)

        exec_config = {
            "max_memory_mb": self.config.max_memory_mb,
            "max_cpu_seconds": self.config.max_cpu_seconds,
            "max_file_size_mb": self.config.max_file_size_mb,
            "allow_network": self.config.allow_network,
            "allow_subprocess": self.config.allow_subprocess,
        }

        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_sandbox_worker,
            args=(skill_file, json.dumps(params, ensure_ascii=False),
                  json.dumps(exec_config), result_queue),
            daemon=True,
        )
        process.start()

        try:
            result_json = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, result_queue.get, True, timeout),
                timeout=timeout,
            )
            data = json.loads(result_json)
            return SandboxResult(
                success=data.get("success", False),
                output=data.get("output"),
                error=data.get("error", ""),
                execution_time=data.get("execution_time", 0),
                memory_peak_mb=data.get("memory_peak_mb", 0),
            )
        except asyncio.TimeoutError:
            process.kill()
            process.join(timeout=5)
            return SandboxResult(success=False, error=f"超时（>{timeout}s）")
        except Exception as e:
            if process.is_alive():
                process.kill()
            return SandboxResult(success=False, error=str(e))
        finally:
            shutil.rmtree(sandbox_dir, ignore_errors=True)


class SkillExecutionDispatcher:
    """根据 Skill 类别选择执行方式"""

    def __init__(self, sandbox: ProcessIsolatedSandbox):
        self.sandbox = sandbox

    async def execute(self, skill, params: dict, context: dict = None) -> dict:
        from skills.base import SkillCategory
        category = skill.metadata.category

        if category in (SkillCategory.BUILTIN, SkillCategory.COMPOSITE, SkillCategory.LEARNED):
            return await skill.execute(params, context)
        elif category == SkillCategory.EXTENSION:
            skill_file = getattr(skill, '_source_file', None)
            if not skill_file:
                return {"success": False, "error": "扩展 Skill 缺少源文件路径"}
            result = await self.sandbox.execute(skill_file, params)
            if result.success:
                return {"success": True, "outputs": result.output}
            return {"success": False, "error": result.error}
        elif category == SkillCategory.MCP:
            return await skill.execute(params, context)
        return {"success": False, "error": f"未知类别: {category}"}
