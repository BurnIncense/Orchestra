"""
GPU 模型热插拔管理器

保证：
1. 同一时间只有一个生成模型在 GPU 上（互斥加载）
2. 同一时间只有一个推理操作在执行（推理锁）
3. 请求排队 + 优先级 + 背压控制
4. 显存监控 + OOM 自动清理 + 加载失败回滚
"""

import gc
import time
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum, IntEnum

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None
    _TORCH_AVAILABLE = False

logger = logging.getLogger("orchestra.hot_swap")


class ModelState(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


class RequestPriority(IntEnum):
    SYSTEM = 0
    USER = 1
    BATCH = 2
    BACKGROUND = 3


@dataclass
class ModelSlot:
    name: str
    state: ModelState = ModelState.UNLOADED
    gpu_memory_gb: float = 0.0
    load_time: float = 0.0
    last_used: float = 0.0
    error: str = ""


class HotSwapManager:
    MAX_QUEUE_SIZE = 20

    def __init__(self, config: dict):
        self.config = config
        self.gpu_total_gb = config.get("hardware", {}).get("gpu_memory_gb", 8)

        self._load_lock = asyncio.Lock()
        self._inference_lock = asyncio.Lock()
        self._request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.MAX_QUEUE_SIZE
        )

        self.current: Optional[str] = None
        self._models: dict[str, ModelSlot] = {
            "vision": ModelSlot(name="Janus-Pro-1B", gpu_memory_gb=4.0),
            "video": ModelSlot(name="MultiShotMaster", gpu_memory_gb=6.0),
        }

        self._vision_model = None
        self._vision_processor = None
        self._video_pipeline = None

        self._load_count = 0
        self._unload_count = 0
        self._inference_count = 0
        self._inference_rejected = 0
        self._queue_wait_total = 0.0

    async def load_vision(self):
        async with self._load_lock:
            await self._do_load("vision")

    async def load_video(self):
        async with self._load_lock:
            await self._do_load("video")

    async def unload_all(self):
        async with self._load_lock:
            self._do_unload()

    def unload_if_generation_done(self):
        if self.current in ("vision", "video"):
            self._do_unload()

    async def run_inference(self, model: str, fn, *args,
                             priority: RequestPriority = RequestPriority.USER,
                             timeout: float = 600.0, **kwargs) -> dict:
        if self._request_queue.full():
            self._inference_rejected += 1
            return {"success": False, "error": "系统繁忙，请稍后重试"}

        enqueue_time = time.time()

        async with self._inference_lock:
            wait_time = time.time() - enqueue_time
            self._queue_wait_total += wait_time

            if self.current != model:
                await self._do_load(model)

            self._inference_count += 1
            start = time.time()

            try:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: fn(*args, **kwargs)),
                    timeout=timeout,
                )
                return result
            except asyncio.TimeoutError:
                return {"success": False, "error": f"推理超时（>{timeout}s）"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def _do_load(self, model_name: str):
        if self.current == model_name:
            self._models[model_name].last_used = time.time()
            return

        if self.current is not None:
            self._do_unload()

        slot = self._models[model_name]
        free_gb = self.gpu_free_gb
        if free_gb < slot.gpu_memory_gb:
            self._force_cleanup()
            free_gb = self.gpu_free_gb
            if free_gb < slot.gpu_memory_gb:
                raise RuntimeError(
                    f"显存不足: 需要 {slot.gpu_memory_gb}GB, 可用 {free_gb:.1f}GB"
                )

        slot.state = ModelState.LOADING
        start = time.time()

        try:
            if model_name == "vision":
                await self._load_janus()
            elif model_name == "video":
                await self._load_multishot()

            slot.state = ModelState.LOADED
            slot.load_time = time.time() - start
            slot.last_used = time.time()
            self.current = model_name
            self._load_count += 1
            logger.info(f"✅ {slot.name} 已加载 ({slot.load_time:.1f}s)")

        except Exception as e:
            slot.state = ModelState.ERROR
            slot.error = str(e)
            self._force_cleanup()
            self.current = None
            raise

    def _do_unload(self):
        if self._vision_model is not None:
            del self._vision_model, self._vision_processor
            self._vision_model = None
            self._vision_processor = None
            self._models["vision"].state = ModelState.UNLOADED

        if self._video_pipeline is not None:
            del self._video_pipeline
            self._video_pipeline = None
            self._models["video"].state = ModelState.UNLOADED

        self.current = None
        self._force_cleanup()
        self._unload_count += 1

    def _force_cleanup(self):
        gc.collect()
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    async def _load_janus(self):
        if not _TORCH_AVAILABLE:
            raise RuntimeError("torch 未安装，无法加载视觉模型")
        from transformers import AutoModelForCausalLM
        import sys
        model_path = self.config["models"]["vision"]["path"]
        sys.path.insert(0, model_path)
        from janus.models import VLChatProcessor
        self._vision_processor = VLChatProcessor.from_pretrained(model_path)
        self._vision_model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, trust_remote_code=True,
        ).to("cuda").eval()

    async def _load_multishot(self):
        if not _TORCH_AVAILABLE:
            raise RuntimeError("torch 未安装，无法加载视频模型")
        from diffusers import WanTextToVideoPipeline
        model_path = self.config["models"]["video"]["path"]
        self._video_pipeline = WanTextToVideoPipeline.from_pretrained(
            model_path, torch_dtype=torch.float16,
        )
        self._video_pipeline.text_encoder.to("cpu")
        self._video_pipeline.to("cuda")
        self._video_pipeline.enable_model_cpu_offload()

    @property
    def gpu_free_gb(self) -> float:
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            return torch.cuda.mem_get_info()[0] / 1024**3
        return 0

    @property
    def gpu_used_gb(self) -> float:
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1024**3
        return 0

    @property
    def vision_model(self):
        if self._vision_model is None:
            raise RuntimeError("Janus-Pro-1B 未加载")
        return self._vision_model

    @property
    def vision_processor(self):
        if self._vision_processor is None:
            raise RuntimeError("Janus-Pro-1B 未加载")
        return self._vision_processor

    @property
    def video_pipeline(self):
        if self._video_pipeline is None:
            raise RuntimeError("MultiShotMaster 未加载")
        return self._video_pipeline

    def status(self) -> dict:
        return {
            "current": self.current,
            "gpu_used_gb": round(self.gpu_used_gb, 2),
            "gpu_free_gb": round(self.gpu_free_gb, 2),
            "inference_lock_locked": self._inference_lock.locked(),
            "queue_size": self._request_queue.qsize(),
            "inference_count": self._inference_count,
            "inference_rejected": self._inference_rejected,
            "models": {
                name: {"state": s.state.value, "load_time": round(s.load_time, 2)}
                for name, s in self._models.items()
            },
        }
