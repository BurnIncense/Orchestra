import logging
import os
import time

logger = logging.getLogger("orchestra.llm")


class LLMClient:
    def __init__(self, base_url: str, alias: str = ""):
        self.base_url = base_url.rstrip("/")
        self.alias = alias

    def _get_http_client(self):
        try:
            import httpx
            return httpx.Client(timeout=30.0)
        except ImportError:
            import requests
            return requests

    def is_available(self) -> bool:
        try:
            client = self._get_http_client()
            if hasattr(client, "get"):
                resp = client.get(f"{self.base_url}/v1/models", timeout=5.0)
            else:
                resp = client.request("GET", f"{self.base_url}/v1/models", timeout=5.0)
            if hasattr(resp, "status_code"):
                return resp.status_code == 200
            return True
        except Exception:
            return False

    def chat(self, prompt: str, system: str = "", history: list = None,
             max_tokens: int = 1024, temperature: float = 0.7) -> dict:
        if history is None:
            history = []

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.alias,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(3):
            try:
                client = self._get_http_client()
                if hasattr(client, "post"):
                    resp = client.post(
                        f"{self.base_url}/v1/chat/completions",
                        json=payload,
                        timeout=30.0,
                    )
                else:
                    resp = client.request(
                        "POST",
                        f"{self.base_url}/v1/chat/completions",
                        json=payload,
                        timeout=30.0,
                    )

                if hasattr(resp, "raise_for_status"):
                    resp.raise_for_status()

                data = resp.json() if hasattr(resp, "json") else resp.json

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {"content": content, "usage": usage}

            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))

        raise RuntimeError(f"LLM 调用失败: {last_error}")


class MockLLM:
    """模拟 LLM — 当模型不可用时使用，返回预设回复"""

    def __init__(self, alias: str = "mock"):
        self.alias = alias

    @property
    def is_available(self) -> bool:
        return True

    def chat(self, prompt: str, system: str = "", history: list = None,
             max_tokens: int = 1024, temperature: float = 0.7) -> dict:
        responses = [
            f"我是 Orchestra AI（演示模式）。你说的是：「{prompt[:50]}」",
            "这是模拟回复。要启用真实 AI，请下载模型并配置模型路径。",
            f"收到你的消息了（{len(prompt)} 字符）。当前运行在无模型降级模式。",
        ]
        import random
        content = random.choice(responses)
        return {"content": content, "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


def create_llm_engine(model_config: dict) -> object:
    """根据配置创建 LLM 引擎

    优先级：
    1. llama_cpp 嵌入式（backend=llama_cpp 且模型文件存在）
    2. HTTP 远程服务（backend=http 或端口配置）
    3. Mock 模拟（都不可用时）

    返回的对象统一具有 chat() 和 is_available 接口
    """
    backend = model_config.get("backend", "llama_cpp")
    model_path = model_config.get("path", "")
    alias = model_config.get("name", "llm")

    if backend == "llama_cpp" and model_path and os.path.exists(model_path):
        try:
            from models.llama_engine import LlamaEngine
            engine = LlamaEngine(
                model_path=model_path,
                n_ctx=model_config.get("n_ctx", 4096),
                n_gpu_layers=model_config.get("n_gpu_layers", 0),
                alias=alias,
            )
            if engine.is_available:
                return engine
        except Exception as e:
            logger.warning(f"llama.cpp 引擎初始化失败: {e}，尝试 HTTP 模式")

    port = model_config.get("port")
    if port:
        try:
            client = LLMClient(f"http://localhost:{port}", alias)
            if client.is_available():
                return client
        except Exception as e:
            logger.warning(f"HTTP LLM 服务不可用: {e}")

    logger.warning(f"⚠️ 模型 {alias} 未找到，使用模拟模式")
    return MockLLM(alias)


def create_thinker(port_or_config=None):
    """创建 Thinker 引擎（推理模型）

    兼容旧调用（传 port int）和新调用（传 dict 配置）
    """
    if isinstance(port_or_config, int):
        return LLMClient(f"http://localhost:{port_or_config}", "minicpm-thinker")
    if isinstance(port_or_config, dict):
        return create_llm_engine(port_or_config)
    return MockLLM("minicpm-thinker")


def create_memory_llm(port_or_config=None):
    """创建 Memory 引擎（记忆模型）"""
    if isinstance(port_or_config, int):
        return LLMClient(f"http://localhost:{port_or_config}", "qwen-memory")
    if isinstance(port_or_config, dict):
        return create_llm_engine(port_or_config)
    return MockLLM("qwen-memory")
