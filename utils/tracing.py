"""
分布式追踪 — Trace ID 全链路传播

每个用户请求生成唯一 trace_id，通过 contextvars 在所有协程间传播。
"""

import uuid
import time
import contextvars
import logging
import json
import os
from dataclasses import dataclass, field

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_span_stack_var: contextvars.ContextVar[list] = contextvars.ContextVar("span_stack", default=[])


def new_trace() -> str:
    trace_id = f"orc_{uuid.uuid4().hex[:16]}"
    _trace_id_var.set(trace_id)
    _span_stack_var.set([])
    return trace_id


def get_trace_id() -> str:
    return _trace_id_var.get()


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    name: str = ""
    module: str = ""
    start_time: float = 0
    end_time: float = 0
    status: str = "ok"
    attributes: dict = field(default_factory=dict)
    error: str = ""

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "module": self.module,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "error": self.error,
        }


class Tracer:
    def __init__(self, log_dir: str = "./data/traces"):
        self.log_dir = log_dir
        self._spans: list[Span] = []
        self._logger = logging.getLogger("orchestra.trace")

    def start_span(self, name: str, module: str = "", attributes: dict = None) -> Span:
        trace_id = get_trace_id()
        stack = _span_stack_var.get()
        parent_id = stack[-1].span_id if stack else ""
        span = Span(
            trace_id=trace_id,
            span_id=f"sp_{uuid.uuid4().hex[:8]}",
            parent_span_id=parent_id,
            name=name, module=module,
            start_time=time.time(),
            attributes=attributes or {},
        )
        stack.append(span)
        _span_stack_var.set(stack)
        return span

    def end_span(self, span: Span, error: str = ""):
        span.end_time = time.time()
        span.status = "error" if error else "ok"
        span.error = error
        stack = _span_stack_var.get()
        if stack and stack[-1].span_id == span.span_id:
            stack.pop()
            _span_stack_var.set(stack)
        self._spans.append(span)
        self._logger.info(json.dumps(span.to_dict(), ensure_ascii=False))

    def flush(self):
        os.makedirs(self.log_dir, exist_ok=True)
        path = os.path.join(self.log_dir, f"traces_{int(time.time())}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for span in self._spans:
                f.write(json.dumps(span.to_dict(), ensure_ascii=False) + "\n")
        self._spans.clear()


tracer = Tracer()


def traced(name: str = "", module: str = ""):
    """自动追踪装饰器"""
    import functools
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            span = tracer.start_span(name or fn.__name__, module)
            try:
                result = await fn(*args, **kwargs)
                tracer.end_span(span)
                return result
            except Exception as e:
                tracer.end_span(span, error=str(e))
                raise
        return wrapper
    return decorator
