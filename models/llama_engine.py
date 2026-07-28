"""llama.cpp 嵌入式引擎 — 本地 GGUF 模型推理"""
import os
import logging
import threading
from typing import Optional

logger = logging.getLogger("orchestra.llama")


class LlamaEngine:
    """基于 llama-cpp-python 的本地推理引擎

    支持：
    - GGUF 格式模型加载
    - Chat Completions 接口（OpenAI 兼容）
    - CPU/GPU 自动检测
    - 线程锁保证并发安全
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        n_threads: int = None,
        alias: str = "",
    ):
        self.model_path = os.path.abspath(model_path)
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads or (os.cpu_count() or 4)
        self.alias = alias or os.path.basename(model_path)
        self._model = None
        self._lock = threading.Lock()
        self._loaded = False

        if not os.path.exists(self.model_path):
            logger.warning(f"模型文件不存在: {self.model_path}")
            return

        self._load_model()

    def _load_model(self):
        """加载模型到内存"""
        try:
            from llama_cpp import Llama

            logger.info(f"加载模型: {self.model_path}")
            logger.info(f"  n_ctx={self.n_ctx}, n_gpu_layers={self.n_gpu_layers}, n_threads={self.n_threads}")

            self._model = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_threads=self.n_threads,
                verbose=False,
            )
            self._loaded = True
            logger.info(f"✅ 模型加载完成: {self.alias}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self._model = None
            self._loaded = False

    @property
    def is_available(self) -> bool:
        return self._loaded and self._model is not None

    def chat(
        self,
        prompt: str,
        system: str = "",
        history: list = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict:
        """聊天补全（OpenAI 兼容格式）

        返回: {"content": str, "usage": dict}
        """
        if not self.is_available:
            raise RuntimeError(f"模型未加载: {self.alias}")

        if history is None:
            history = []

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        with self._lock:
            try:
                output = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                content = output["choices"][0]["message"]["content"]
                usage = output.get("usage", {})
                return {"content": content, "usage": usage}
            except Exception as e:
                logger.error(f"推理失败: {e}")
                raise RuntimeError(f"LLM 推理失败: {e}")

    def unload(self):
        """卸载模型释放内存"""
        if self._model is not None:
            del self._model
            self._model = None
            self._loaded = False
            logger.info(f"模型已卸载: {self.alias}")

    def __del__(self):
        self.unload()
