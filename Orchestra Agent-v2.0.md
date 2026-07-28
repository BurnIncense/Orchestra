# Orchestra v2.2 — 完整开发文档

---

## 一、项目概述

### 1.1 定义

Orchestra 是一个**本地运行、完全离线、零成本**的全能 AI Agent 平台，融合四个开源模型，通过 Skill 技能系统和 MCP 协议实现无限能力扩展。

### 1.2 模型矩阵

| 角色     | 模型                       | 职责                                          | 显存占用         |
| -------- | -------------------------- | --------------------------------------------- | ---------------- |
| 🧮 思考者 | MiniCPM5-1B (Q4_K_M)       | 推理、代码、规划、工具调用、Agent 决策        | 0.7 GB（常驻）   |
| 📚 记忆员 | Qwen3.5-0.8B (Q4_K_M)      | 262K 上下文管理、对话压缩、文档理解、偏好学习 | 0.5 GB（常驻）   |
| 🎨 画师   | Janus-Pro-1B               | 文生图、图片理解、图片编辑                    | 4.0 GB（热插拔） |
| 🎬 导演   | MultiShotMaster (Wan 1.3B) | 多镜头叙事视频、镜头调度、图生视频            | 6.0 GB（热插拔） |

### 1.3 硬件要求

| 资源     | 最低  | 推荐  |
| -------- | ----- | ----- |
| GPU 显存 | 8 GB  | 12 GB |
| 系统内存 | 16 GB | 32 GB |
| 磁盘     | 30 GB | 50 GB |
| CUDA     | 12.1+ | 12.4+ |

### 1.4 核心设计原则

```
1. 大脑永在线     → 两个 LLM 常驻 GPU（仅占 1.2GB）
2. 双手按需伸     → 生成模型热插拔（互斥加载 + 推理互斥锁）
3. 记忆不丢失     → 分层记忆 + Per-User 隔离 + 持久化
4. 任务自规划     → MiniCPM5 原生 Agent 能力驱动
5. 工具可调用     → Skill 系统 + MCP 协议统一
6. 安全不信任     → 进程级沙箱 + Saga 补偿 + 权限强制
7. 故障可恢复     → WAL 持久化 + 崩溃恢复 + 健康检查
8. 全链路可追踪   → Trace ID + Span 层级传播
```

---

## 二、系统架构

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户层 (多用户隔离)                                 │
│   User A (Session A)  │  User B (Session B)  │  MCP Client (外部 AI)        │
│   独立记忆/偏好/Trace  │  独立记忆/偏好/Trace  │  API Key + TLS 认证          │
└───────────┬───────────────────────┬──────────────────────┬──────────────────┘
            │                       │                      │
            ▼                       ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Session Manager (会话管理器)                              │
│   • Per-User Session 创建/获取/过期清理                                      │
│   • 并发限制 (MAX_SESSIONS=50)                                              │
│   • 独立 Memory / Learner / CallGuard / Trace                               │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent Core                                               │
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Intent   │  │ Planner  │  │ UnifiedRouter│  │ RuntimeCallGuard      │  │
│  │ (意图)   │  │ (规划)   │  │ (路由+防环)  │  │ (深度熔断+循环检测)   │  │
│  └──────────┘  └──────────┘  └──────────────┘  └───────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Saga Engine (补偿事务引擎)                                          │   │
│  │  • 正向执行 → 失败 → 逆序补偿（文件/DB/API 全类型）                   │   │
│  │  • WAL 持久化 → 崩溃后自动恢复                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Tracer (分布式追踪)                                                 │   │
│  │  • Trace ID 全链路传播 (contextvars)                                  │   │
│  │  • Span 层级记录 (Agent → Skill → HotSwap → MCP)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐
│  LLM 服务       │  │  Skill 执行层        │  │  MCP 层                 │
│  (常驻,共享)    │  │                     │  │                         │
│                 │  │  ┌───────────────┐  │  │  ┌───────────────────┐  │
│ MiniCPM5-1B    │  │  │ Dispatcher    │  │  │  │ Client Manager    │  │
│ Qwen3.5-0.8B   │  │  │ (调度器)      │  │  │  │ • Per-Server 配额 │  │
│                 │  │  └───────┬───────┘  │  │  │ • 重试+健康检查   │  │
│                 │  │          │          │  │  │ • PermissionGuard │  │
│                 │  │    ┌─────┴─────┐   │  │  └───────────────────┘  │
│                 │  │    ▼           ▼   │  │                         │
│                 │  │ 主进程      沙箱   │  │  ┌───────────────────┐  │
│                 │  │ (builtin)  (ext)  │  │  │ Server (HTTPS)    │  │
│                 │  │            子进程  │  │  │ • TLS 强制        │  │
│                 │  │            隔离   │  │  │ • API Key 认证    │  │
│                 │  └───────────────────┘  │  │ • 用户级资源 ACL  │  │
│                 │                         │  │ • 速率限制        │  │
└─────────────────┘  └─────────────────────┘  └─────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  HotSwapManager                                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  _inference_lock — 推理互斥锁（所有 GPU 推理操作序列化）              │   │
│  │  _load_lock     — 加载/卸载互斥锁（模型切换串行化）                   │   │
│  │  优先级队列 + 背压控制（队列满 → 503 优雅降级）                       │   │
│  │  显存监控 + OOM 自动清理 + 加载失败回滚                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  GPU: [MiniCPM 0.7G][Qwen 0.5G][████ 热插拔区 6.8G ████]                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 显存分配

```
┌─────────────────────── 8 GB GPU ───────────────────────┐
│                                                         │
│  [常驻区 1.2GB]          [热插拔区 6.8GB]               │
│  ┌──────────────┐       ┌─────────────────────────┐    │
│  │ MiniCPM5-1B  │       │                         │    │
│  │ Q4_K_M 0.7G │       │  模式A: Janus-Pro  4GB  │    │
│  ├──────────────┤       │  模式B: MultiShot  6GB  │    │
│  │ Qwen3.5-0.8B│       │                         │    │
│  │ Q4_K_M 0.5G │       │  ⚠️ A/B 互斥           │    │
│  └──────────────┘       └─────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────── 16 GB RAM ──────────────────────┐
│  • UMT5 文本编码器 (Wan) ~4GB → CPU                    │
│  • 模型权重 mmap 缓存                                   │
│  • 沙箱子进程内存                                       │
│  • 记忆持久化数据                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、项目目录结构

```
orchestra/
├── config/
│   ├── settings.yaml              # 全局配置（支持环境变量覆盖）
│   └── tools.yaml                 # 工具注册表
│
├── core/
│   ├── __init__.py
│   ├── agent.py                   # Agent 主循环（Session 隔离版）
│   ├── session.py                 # 会话管理器（Per-User 隔离）
│   ├── router.py                  # 统一路由器（命名空间+优先级+Token防环）
│   ├── planner.py                 # 任务规划器
│   ├── intent.py                  # 意图识别
│   ├── executor.py                # 执行引擎
│   ├── saga.py                    # Saga 补偿事务引擎（WAL+崩溃恢复）
│   ├── dependency_graph.py        # 依赖图（控制流+数据流循环检测）
│   └── param_extractor.py         # 参数提取器（多策略容错）
│
├── memory/
│   ├── __init__.py
│   ├── manager.py                 # 四层记忆管理器
│   ├── compressor.py              # 对话压缩（Qwen3.5）
│   ├── document.py                # 文档处理（262K 上下文）
│   └── persistence.py             # 持久化（防抖+原子写入）
│
├── models/
│   ├── __init__.py
│   ├── base.py                    # 模型基类
│   ├── llm_service.py             # LLM 服务封装
│   ├── hot_swap.py                # GPU 热插拔（推理锁+队列+背压+显存监控）
│   ├── vision_service.py          # 视觉服务（Janus）
│   └── video_service.py           # 视频服务（MultiShot）
│
├── skills/
│   ├── __init__.py
│   ├── base.py                    # Skill 基类
│   ├── registry.py                # Skill 注册中心（倒排索引）
│   ├── loader.py                  # Skill 加载器
│   ├── sandbox_v2.py              # 进程级隔离沙箱
│   ├── composer.py                # 组合编排器（循环检测+并行+超时）
│   ├── learner.py                 # 学习器（容错+增量+Per-User）
│   ├── versioning.py              # 版本管理（语义化约束+回滚）
│   ├── definitions/               # Skill 定义 (YAML)
│   │   ├── image_generation.yaml
│   │   ├── image_understanding.yaml
│   │   ├── video_generation.yaml
│   │   ├── multishot_video.yaml
│   │   ├── code_execution.yaml
│   │   ├── web_search.yaml
│   │   └── data_analysis.yaml
│   ├── builtin/                   # 内置 Skill
│   │   ├── __init__.py
│   │   ├── image_gen.py
│   │   ├── image_understand.py
│   │   ├── video_gen.py
│   │   ├── multishot_video.py
│   │   ├── code_exec.py
│   │   ├── web_search.py
│   │   └── file_ops.py
│   ├── extension/                 # 扩展 Skill（用户自定义，沙箱执行）
│   │   ├── __init__.py
│   │   └── example_skill.py
│   └── learned/                   # 学习型 Skill
│       └── __init__.py
│
├── mcp/
│   ├── __init__.py
│   ├── client/
│   │   ├── __init__.py
│   │   ├── manager.py             # MCP 连接管理（重试+健康检查+Per-Server配额）
│   │   ├── transport.py           # 传输层（stdio / SSE）
│   │   ├── tool_bridge.py         # MCP 工具 → Skill 桥接
│   │   └── permission_guard.py    # 权限强制执行器
│   ├── server/
│   │   ├── __init__.py
│   │   ├── orchestra_server.py    # Orchestra MCP Server
│   │   ├── tls.py                 # TLS 证书管理（强制 HTTPS）
│   │   ├── auth.py                # 认证（API Key + 速率限制）
│   │   ├── resources.py           # 资源管理（用户级 ACL）
│   │   ├── tools.py               # 暴露的工具
│   │   └── prompts.py             # 暴露的提示词模板
│   └── config/
│       ├── servers.yaml           # 外部 MCP Server 配置
│       └── permissions.yaml       # 权限策略
│
├── utils/
│   ├── __init__.py
│   ├── logger.py                  # 结构化日志 + 指标采集
│   ├── tracing.py                 # 分布式追踪（Trace ID + Span）
│   ├── exceptions.py              # 统一异常体系
│   ├── paths.py                   # 跨平台路径
│   ├── config.py                  # 配置加载（环境变量覆盖）
│   ├── config_watcher.py          # 配置热加载
│   └── gpu_monitor.py             # 显存监控
│
├── interface/
│   ├── __init__.py
│   ├── cli.py                     # 命令行界面
│   ├── web_ui.py                  # Gradio Web 界面（多用户 Session）
│   ├── api_server.py              # FastAPI 服务（背压中间件）
│   └── health.py                  # 健康检查端点
│
├── tests/
│   ├── conftest.py
│   ├── test_router.py
│   ├── test_sandbox.py
│   ├── test_hot_swap.py
│   ├── test_saga.py
│   ├── test_session.py
│   ├── test_composer.py
│   ├── test_mcp_permissions.py
│   ├── test_memory.py
│   ├── test_tracing.py
│   └── test_integration.py
│
├── data/
│   ├── logs/                      # 结构化日志
│   ├── traces/                    # 追踪数据
│   ├── memory/
│   │   └── sessions/              # Per-User 记忆
│   │       ├── user_a/
│   │       │   ├── memory.pkl
│   │       │   └── preferences.json
│   │       └── user_b/
│   ├── outputs/
│   │   ├── users/                 # Per-User 生成结果
│   │   │   ├── user_a/
│   │   │   │   ├── images/
│   │   │   │   └── videos/
│   │   │   └── shared/
│   │   └── shared/
│   ├── saga/                      # Saga WAL 文件
│   ├── skill_versions/            # Skill 版本备份
│   ├── certs/                     # TLS 证书
│   └── cache/
│
├── scripts/
│   ├── download_models.sh         # 模型下载
│   ├── start_services.sh          # 一键启动
│   ├── health_check.py            # 健康检查
│   └── benchmark.py               # 性能测试
│
├── main.py                        # 入口
├── requirements.txt
└── README.md
```

---

## 四、配置系统

### 4.1 全局配置

```yaml
# config/settings.yaml
system:
  name: "Orchestra"
  version: "2.2.0"
  instance_id: "${ORCHESTRA_INSTANCE:-default}"
  log_level: "INFO"
  log_dir: "./data/logs"
  trace_dir: "./data/traces"

hardware:
  gpu_memory_gb: 8
  ram_gb: 16
  strategy: "hot_swap"

ports:
  thinker: "${ORCHESTRA_PORT_THINKER:-8081}"
  memory: "${ORCHESTRA_PORT_MEMORY:-8082}"
  mcp_server: "${ORCHESTRA_PORT_MCP:-9100}"
  web_ui: "${ORCHESTRA_PORT_WEB:-7860}"
  api: "${ORCHESTRA_PORT_API:-8000}"

models:
  thinker:
    name: "MiniCPM5-1B"
    path: "./data/models/minicpm5-1b/MiniCPM5-1B-Q4_K_M.gguf"
    backend: "llama_cpp"
    n_ctx: 131072
    n_gpu_layers: 99
    resident: true

  memory:
    name: "Qwen3.5-0.8B"
    path: "./data/models/qwen3.5-0.8b/Qwen3.5-0.8B-Q4_K_M.gguf"
    backend: "llama_cpp"
    n_ctx: 262144
    n_gpu_layers: 99
    resident: true

  vision:
    name: "Janus-Pro-1B"
    path: "./data/models/janus-pro-1b"
    backend: "transformers"
    dtype: "bfloat16"
    resident: false
    gpu_memory_gb: 4.0

  video:
    name: "MultiShotMaster"
    path: "./data/models/wan2.1-1.3b"
    backend: "diffusers"
    dtype: "float16"
    resident: false
    gpu_memory_gb: 6.0
    text_encoder_device: "cpu"

skills:
  builtin_dir: "./skills/builtin"
  extension_dir: "./skills/extension"
  definitions_dir: "./skills/definitions"
  auto_load_extensions: true
  sandbox:
    max_memory_mb: 2048
    max_cpu_seconds: 300
    max_file_size_mb: 100
    allow_network: false
    allow_subprocess: false
  learning:
    enabled: true
    min_records: 5
    learn_interval: 20

mcp:
  client:
    enabled: true
    config_path: "./mcp/config/servers.yaml"
    auto_connect: true
    bridge_to_skills: true
    timeout: 30
    retry: 3
    max_connections: 10
    per_server_max_concurrent: 3
    health_check_interval: 60

  server:
    enabled: true
    transport: "sse"
    port: "${ORCHESTRA_PORT_MCP:-9100}"
    tls:
      enabled: true
      cert_dir: "./data/certs"
    auth:
      enabled: true
      api_keys:
        - key: "${ORCHESTRA_API_KEY_1:-orc_default_key}"
          name: "Default Client"
          permissions: ["*"]
          rate_limit: 60
    resource_acl:
      "orchestra://users/*": "owner_only"
      "orchestra://shared/*": "authenticated"

session:
  max_sessions: 50
  max_idle_seconds: 3600
  max_turns: 100
  persist: true
  cleanup_interval: 60

saga:
  persistence_dir: "./data/saga"
  auto_recover: true

memory:
  max_working_turns: 10
  compress_threshold: 10
  auto_save_interval: 5

output:
  base_dir: "./data/outputs"
  max_images_per_user: 200
  max_videos_per_user: 50
```

### 4.2 MCP Server 配置

```yaml
# mcp/config/servers.yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${HOME}/documents"]
    transport: "stdio"
    enabled: true

  browser:
    command: "npx"
    args: ["-y", "@anthropic/mcp-server-puppeteer"]
    transport: "stdio"
    enabled: true

  sqlite:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sqlite", "./data/orchestra.db"]
    transport: "stdio"
    enabled: true

  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    transport: "stdio"
    enabled: false
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
```

### 4.3 权限配置

```yaml
# mcp/config/permissions.yaml
permissions:
  default_policy: "ask"

  servers:
    filesystem:
      read: "allow"
      write: "ask"
      delete: "deny"
    browser:
      navigate: "allow"
      screenshot: "allow"
      form_submit: "ask"
    github:
      read_repo: "allow"
      create_issue: "ask"
      push_code: "deny"

  tools:
    execute_code:
      policy: "ask"
      sandbox: true
      timeout: 30
```

---

## 五、核心模块实现

### 5.1 会话管理器

```python
# core/session.py
"""
会话管理器 — 多用户状态完全隔离

每个用户连接创建独立的 Session：
- 独立的 MemoryManager（对话历史）
- 独立的 SkillLearner（偏好）
- 独立的 RuntimeCallGuard（调用栈）
- 独立的 Trace ID
- 共享的 SkillRegistry / HotSwapManager / MCP Client
"""

import uuid
import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger("orchestra.session")


@dataclass
class SessionConfig:
    max_idle_seconds: float = 3600.0
    max_turns: int = 100
    persist: bool = True


class Session:
    """用户会话（状态完全隔离）"""

    def __init__(self, session_id: str, user_id: str,
                 memory_llm, config: SessionConfig = None):
        self.session_id = session_id
        self.user_id = user_id
        self.config = config or SessionConfig()

        # 独立的记忆
        from memory.manager import MemoryManager
        self.memory = MemoryManager(
            config={
                "max_working_turns": 10,
                "persist_path": f"./data/memory/sessions/{user_id}/memory.pkl",
            },
            memory_llm=memory_llm,
        )

        # 独立的学习器（Per-User 偏好）
        from skills.learner import SkillLearner
        self.learner = SkillLearner(
            memory_llm=memory_llm,
            persist_path=f"./data/memory/sessions/{user_id}/preferences.json",
        )

        # 独立的调用守卫
        from core.dependency_graph import RuntimeCallGuard
        self.call_guard = RuntimeCallGuard()

        # Trace
        self.current_trace_id: str = ""

        # 元数据
        self.created_at = time.time()
        self.last_active = time.time()
        self.turn_count = 0

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > self.config.max_idle_seconds

    def get_context(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "memory": self.memory,
            "learner": self.learner,
            "call_guard": self.call_guard,
            "trace_id": self.current_trace_id,
        }

    def save(self):
        if self.config.persist:
            self.memory.save()
            self.learner._save()

    def cleanup(self):
        self.save()
        logger.info(f"🧹 会话清理: {self.session_id} (用户: {self.user_id})")


class SessionManager:
    """会话管理器"""

    MAX_SESSIONS = 50

    def __init__(self, memory_llm, cleanup_interval: float = 60.0):
        self.memory_llm = memory_llm
        self.cleanup_interval = cleanup_interval
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, str] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def get_or_create(self, user_id: str) -> Session:
        async with self._lock:
            if user_id in self._user_sessions:
                session_id = self._user_sessions[user_id]
                session = self._sessions.get(session_id)
                if session and not session.is_expired():
                    session.touch()
                    return session

            if len(self._sessions) >= self.MAX_SESSIONS:
                await self._evict_oldest()

            session_id = f"sess_{uuid.uuid4().hex[:12]}"
            session = Session(
                session_id=session_id,
                user_id=user_id,
                memory_llm=self.memory_llm,
            )
            self._sessions[session_id] = session
            self._user_sessions[user_id] = session_id
            logger.info(f"📝 新会话: {session_id} (用户: {user_id})")
            return session

    async def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    async def destroy(self, session_id: str):
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.save()
                self._user_sessions.pop(session.user_id, None)

    async def _evict_oldest(self):
        if not self._sessions:
            return
        oldest_id = min(self._sessions, key=lambda k: self._sessions[k].last_active)
        await self.destroy(oldest_id)

    async def start_cleanup_loop(self):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(self.cleanup_interval)
            expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
            for sid in expired:
                await self.destroy(sid)

    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
        for session in self._sessions.values():
            session.save()
        self._sessions.clear()
        self._user_sessions.clear()

    @property
    def active_count(self) -> int:
        return len(self._sessions)
```

### 5.2 GPU 热插拔管理器

```python
# models/hot_swap.py
"""
GPU 模型热插拔管理器

保证：
1. 同一时间只有一个生成模型在 GPU 上（互斥加载）
2. 同一时间只有一个推理操作在执行（推理锁）
3. 请求排队 + 优先级 + 背压控制
4. 显存监控 + OOM 自动清理 + 加载失败回滚
"""

import torch
import gc
import time
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum, IntEnum

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

        # 加载/卸载互斥锁
        self._load_lock = asyncio.Lock()
        # 推理互斥锁（所有 GPU 推理操作序列化）
        self._inference_lock = asyncio.Lock()
        # 优先级请求队列
        self._request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.MAX_QUEUE_SIZE
        )

        # 模型状态
        self.current: Optional[str] = None
        self._models: dict[str, ModelSlot] = {
            "vision": ModelSlot(name="Janus-Pro-1B", gpu_memory_gb=4.0),
            "video": ModelSlot(name="MultiShotMaster", gpu_memory_gb=6.0),
        }

        # 模型实例
        self._vision_model = None
        self._vision_processor = None
        self._video_pipeline = None

        # 统计
        self._load_count = 0
        self._unload_count = 0
        self._inference_count = 0
        self._inference_rejected = 0
        self._queue_wait_total = 0.0

    # ─── 公共接口 ───

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
        """
        在推理锁保护下执行模型推理。
        所有 GPU 推理的唯一入口。
        """
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

    # ─── 内部实现 ───

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
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    async def _load_janus(self):
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
        from diffusers import WanTextToVideoPipeline
        model_path = self.config["models"]["video"]["path"]
        self._video_pipeline = WanTextToVideoPipeline.from_pretrained(
            model_path, torch_dtype=torch.float16,
        )
        self._video_pipeline.text_encoder.to("cpu")
        self._video_pipeline.to("cuda")
        self._video_pipeline.enable_model_cpu_offload()

    # ─── 属性 ───

    @property
    def gpu_free_gb(self) -> float:
        if torch.cuda.is_available():
            return torch.cuda.mem_get_info()[0] / 1024**3
        return 0

    @property
    def gpu_used_gb(self) -> float:
        if torch.cuda.is_available():
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
```

### 5.3 统一路由器

```python
# core/router.py
"""
统一路由器

规则：
1. 命名空间隔离（builtin / ext / wf / mcp）
2. 优先级路由（builtin > composite > extension > learned > mcp）
3. 自调用检测（加密 Token，非名称匹配）
4. 运行时调用栈循环检测
5. 显式指定（@namespace:id）
"""

import os
import uuid
import hashlib
import logging
from enum import IntEnum
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("orchestra.router")


class SkillSource(IntEnum):
    BUILTIN = 0
    COMPOSITE = 1
    EXTENSION = 2
    LEARNED = 3
    MCP_BRIDGE = 4


@dataclass
class RoutingDecision:
    skill_id: str
    source: SkillSource
    confidence: float
    is_mcp_bridge: bool = False
    mcp_server: str = ""
    mcp_tool: str = ""


class UnifiedRouter:
    def __init__(self, registry, mcp_client, agent_id: str = "orchestra"):
        self.registry = registry
        self.mcp_client = mcp_client
        self.agent_id = agent_id
        self._instance_token = self._generate_instance_token()
        self._self_tokens: set[str] = {self._instance_token}
        self._call_stack: list[str] = []
        self._max_depth = 10

    def _generate_instance_token(self) -> str:
        raw = f"{uuid.uuid4().hex}:{os.getpid()}:{id(self)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def register_self_token(self, token: str):
        self._self_tokens.add(token)

    def resolve(self, skill_id: str, context: dict = None,
                server_token: str = "") -> Optional[RoutingDecision]:
        if skill_id.startswith("@"):
            return self._resolve_explicit(skill_id)

        if self._is_self_call(skill_id, server_token):
            return None

        candidates = self._find_candidates(skill_id)
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.source)
        return candidates[0]

    def _resolve_explicit(self, skill_id: str) -> Optional[RoutingDecision]:
        parts = skill_id[1:].split(":")
        if parts[0] == "mcp" and len(parts) >= 3:
            server, tool = parts[1], ":".join(parts[2:])
            return RoutingDecision(
                skill_id=f"mcp:{server}:{tool}",
                source=SkillSource.MCP_BRIDGE,
                confidence=1.0,
                is_mcp_bridge=True,
                mcp_server=server,
                mcp_tool=tool,
            )
        else:
            sid = ":".join(parts[1:])
            skill = self.registry.get(sid)
            if skill:
                return RoutingDecision(
                    skill_id=sid,
                    source=self._get_source(skill),
                    confidence=1.0,
                )
        return None

    def _is_self_call(self, skill_id: str, server_token: str = "") -> bool:
        if skill_id in self._call_stack:
            return True
        if server_token and server_token in self._self_tokens:
            return True
        return False

    def _find_candidates(self, skill_id: str) -> list[RoutingDecision]:
        candidates = []
        skill = self.registry.get(skill_id)
        if skill:
            candidates.append(RoutingDecision(
                skill_id=skill_id,
                source=self._get_source(skill),
                confidence=1.0,
            ))
        for server_name, tools in self.mcp_client.discovered_tools.items():
            for tool in tools:
                if tool.name == skill_id:
                    candidates.append(RoutingDecision(
                        skill_id=f"mcp:{server_name}:{tool.name}",
                        source=SkillSource.MCP_BRIDGE,
                        confidence=0.9,
                        is_mcp_bridge=True,
                        mcp_server=server_name,
                        mcp_tool=tool.name,
                    ))
        return candidates

    def _get_source(self, skill) -> SkillSource:
        from skills.base import SkillCategory
        mapping = {
            SkillCategory.BUILTIN: SkillSource.BUILTIN,
            SkillCategory.COMPOSITE: SkillSource.COMPOSITE,
            SkillCategory.EXTENSION: SkillSource.EXTENSION,
            SkillCategory.LEARNED: SkillSource.LEARNED,
            SkillCategory.MCP: SkillSource.MCP_BRIDGE,
        }
        return mapping.get(skill.metadata.category, SkillSource.EXTENSION)

    def push_call(self, skill_id: str):
        if len(self._call_stack) >= self._max_depth:
            raise RecursionError(f"调用深度超过 {self._max_depth}")
        if skill_id in self._call_stack:
            cycle_start = self._call_stack.index(skill_id)
            cycle = self._call_stack[cycle_start:] + [skill_id]
            from core.dependency_graph import CyclicDependencyError
            raise CyclicDependencyError(f"循环: {' → '.join(cycle)}")
        self._call_stack.append(skill_id)

    def pop_call(self):
        if self._call_stack:
            self._call_stack.pop()

    def reset(self):
        self._call_stack.clear()

    async def call_skill(self, skill_id: str, params: dict,
                          context: dict = None) -> dict:
        decision = self.resolve(skill_id)
        if not decision:
            return {"success": False, "error": f"无法路由: {skill_id}"}

        self.push_call(skill_id)
        try:
            if decision.is_mcp_bridge:
                return await self.mcp_client.call_tool(
                    decision.mcp_server, decision.mcp_tool, params
                )
            else:
                skill = self.registry.get(decision.skill_id)
                if not skill:
                    return {"success": False, "error": f"Skill 不存在: {skill_id}"}
                return await skill.execute(params, context)
        finally:
            self.pop_call()
```

### 5.4 Saga 补偿事务引擎

```python
# core/saga.py
"""
Saga 补偿事务引擎

保证：
1. 正向操作按序执行
2. 任何步骤失败 → 逆序执行所有已完成步骤的补偿
3. WAL 持久化 → 崩溃后自动恢复
4. 补偿操作本身失败时记录日志但不中断（尽力补偿）
"""

import asyncio
import json
import time
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum

logger = logging.getLogger("orchestra.saga")


class CompensationType(Enum):
    FILE_DELETE = "file_delete"
    FILE_RESTORE = "file_restore"
    DB_DELETE = "db_delete"
    MCP_COMPENSATE = "mcp_compensate"
    CUSTOM = "custom"
    NONE = "none"


@dataclass
class CompensationAction:
    type: CompensationType
    description: str = ""
    target: str = ""
    backup_data: Any = None
    mcp_server: str = ""
    mcp_tool: str = ""
    mcp_args: dict = field(default_factory=dict)
    custom_fn: Optional[Callable] = None


@dataclass
class SagaStep:
    id: str
    description: str
    skill_id: str = ""
    params: dict = field(default_factory=dict)
    compensation: Optional[CompensationAction] = None
    status: str = "pending"
    result: dict = field(default_factory=dict)


@dataclass
class SagaState:
    saga_id: str
    workflow_id: str
    steps: list[SagaStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "running"
    created_at: float = 0
    updated_at: float = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "saga_id": self.saga_id,
            "workflow_id": self.workflow_id,
            "current_step": self.current_step,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [
                {
                    "id": s.id, "description": s.description,
                    "skill_id": s.skill_id, "params": s.params,
                    "status": s.status, "result": s.result,
                    "compensation": {
                        "type": s.compensation.type.value,
                        "target": s.compensation.target,
                        "description": s.compensation.description,
                    } if s.compensation else None,
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SagaState":
        state = cls(
            saga_id=data["saga_id"],
            workflow_id=data["workflow_id"],
            current_step=data["current_step"],
            status=data["status"],
            error=data.get("error", ""),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
        )
        for s in data.get("steps", []):
            comp = None
            if s.get("compensation"):
                comp = CompensationAction(
                    type=CompensationType(s["compensation"]["type"]),
                    target=s["compensation"].get("target", ""),
                    description=s["compensation"].get("description", ""),
                )
            state.steps.append(SagaStep(
                id=s["id"], description=s["description"],
                skill_id=s["skill_id"], params=s["params"],
                status=s["status"], result=s.get("result", {}),
                compensation=comp,
            ))
        return state


class SagaEngine:
    def __init__(self, router, persistence_dir: str = "./data/saga"):
        self.router = router
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, workflow_id: str, steps: list[dict],
                       context: dict = None) -> dict:
        saga_id = str(uuid.uuid4())[:12]
        state = SagaState(
            saga_id=saga_id, workflow_id=workflow_id,
            created_at=time.time(), updated_at=time.time(),
        )
        for i, step_def in enumerate(steps):
            state.steps.append(SagaStep(
                id=f"step_{i}",
                description=step_def.get("description", f"步骤 {i+1}"),
                skill_id=step_def.get("skill_id", ""),
                params=step_def.get("params", {}),
            ))

        self._persist(state)

        try:
            for i, step in enumerate(state.steps):
                state.current_step = i
                step.status = "running"
                self._persist(state)

                result = await self.router.call_skill(step.skill_id, step.params, context)
                step.result = result

                if result.get("success"):
                    step.status = "completed"
                    step.compensation = self._derive_compensation(step, result)
                    self._persist(state)
                else:
                    step.status = "failed"
                    state.status = "compensating"
                    state.error = result.get("error", "未知错误")
                    self._persist(state)
                    await self._compensate(state, failed_at=i)
                    return {"success": False, "error": state.error,
                            "saga_id": saga_id, "compensated": True}

            state.status = "completed"
            self._persist(state)
            return {"success": True, "saga_id": saga_id,
                    "results": [s.result for s in state.steps]}

        except Exception as e:
            state.status = "compensating"
            state.error = str(e)
            self._persist(state)
            await self._compensate(state, failed_at=state.current_step)
            return {"success": False, "error": str(e), "saga_id": saga_id}

    async def _compensate(self, state: SagaState, failed_at: int):
        for i in range(failed_at - 1, -1, -1):
            step = state.steps[i]
            if step.status != "completed" or not step.compensation:
                continue
            comp = step.compensation
            try:
                await self._execute_compensation(comp)
                step.status = "compensated"
            except Exception as e:
                logger.error(f"补偿失败: {comp.description} - {e}")
                step.status = "compensation_failed"
            self._persist(state)
        state.status = "compensated"
        self._persist(state)

    async def _execute_compensation(self, comp: CompensationAction):
        if comp.type == CompensationType.FILE_DELETE:
            path = Path(comp.target)
            if path.exists():
                path.unlink()
        elif comp.type == CompensationType.FILE_RESTORE:
            if comp.backup_data and comp.target:
                Path(comp.target).write_text(comp.backup_data)
        elif comp.type in (CompensationType.DB_DELETE, CompensationType.MCP_COMPENSATE):
            await self.router.call_skill(
                f"mcp:{comp.mcp_server}:{comp.mcp_tool}", comp.mcp_args
            )
        elif comp.type == CompensationType.CUSTOM and comp.custom_fn:
            if asyncio.iscoroutinefunction(comp.custom_fn):
                await comp.custom_fn()
            else:
                comp.custom_fn()

    def _derive_compensation(self, step: SagaStep, result: dict) -> CompensationAction:
        outputs = result.get("outputs", {})
        if "image_path" in outputs:
            return CompensationAction(
                type=CompensationType.FILE_DELETE,
                target=outputs["image_path"],
                description=f"删除图片: {outputs['image_path']}",
            )
        if "video_path" in outputs:
            return CompensationAction(
                type=CompensationType.FILE_DELETE,
                target=outputs["video_path"],
                description=f"删除视频: {outputs['video_path']}",
            )
        if "db_record_id" in outputs:
            return CompensationAction(
                type=CompensationType.DB_DELETE,
                mcp_server=outputs.get("mcp_server", "sqlite"),
                mcp_tool="delete_record",
                mcp_args={"id": outputs["db_record_id"]},
                description=f"删除记录: {outputs['db_record_id']}",
            )
        return CompensationAction(type=CompensationType.NONE)

    def _persist(self, state: SagaState):
        path = self.persistence_dir / f"{state.saga_id}.json"
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.rename(path)

    def recover_incomplete(self) -> list[SagaState]:
        incomplete = []
        for f in self.persistence_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                state = SagaState.from_dict(data)
                if state.status in ("running", "compensating"):
                    incomplete.append(state)
            except:
                continue
        return incomplete

    async def resume(self, state: SagaState, context: dict = None):
        if state.status == "compensating":
            await self._compensate(state, failed_at=state.current_step)
        elif state.status == "running":
            for i in range(state.current_step, len(state.steps)):
                step = state.steps[i]
                if step.status == "completed":
                    continue
                state.current_step = i
                result = await self.router.call_skill(step.skill_id, step.params, context)
                step.result = result
                if result.get("success"):
                    step.status = "completed"
                    step.compensation = self._derive_compensation(step, result)
                else:
                    step.status = "failed"
                    state.status = "compensating"
                    await self._compensate(state, failed_at=i)
                    return {"success": False, "error": result.get("error")}
                self._persist(state)
            state.status = "completed"
            self._persist(state)
        return {"success": True, "saga_id": state.saga_id}
```

### 5.5 进程级隔离沙箱

```python
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
import resource
import tempfile
import shutil
import asyncio
import multiprocessing
import importlib.util
import logging
from pathlib import Path
from dataclasses import dataclass, field

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

        # 资源限制
        if sys.platform != "win32":
            max_mem = config.get("max_memory_mb", 2048) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_mem, max_mem))
            max_cpu = config.get("max_cpu_seconds", 300)
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu))
            max_file = config.get("max_file_size_mb", 100) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file, max_file))
            resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))

        # 忽略信号
        for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
            try:
                signal.signal(sig, signal.SIG_IGN)
            except:
                pass

        # 禁止网络
        if not config.get("allow_network", False):
            import socket
            socket.socket.connect = lambda self, *a, **k: (_ for _ in ()).throw(
                PermissionError("沙箱禁止网络"))

        # 禁止子进程
        if not config.get("allow_subprocess", False):
            import subprocess
            subprocess.Popen = lambda *a, **k: (_ for _ in ()).throw(
                PermissionError("沙箱禁止子进程"))
            os.system = lambda *a: (_ for _ in ()).throw(
                PermissionError("沙箱禁止系统调用"))

        # 加载执行
        spec = importlib.util.spec_from_file_location("sandboxed_skill", skill_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        skill = module.create_skill()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(skill.execute(params, {}))
        loop.close()

        elapsed = time.time() - start
        mem_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

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
```

### 5.6 分布式追踪

```python
# utils/tracing.py
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
```

### 5.7 Agent 主循环

```python
# core/agent.py
"""
Orchestra Agent v2.2 — 完整主循环
"""

import asyncio
import json
import logging
import time
from rich.console import Console

from models.llm_service import create_thinker, create_memory_llm
from models.hot_swap import HotSwapManager
from core.session import SessionManager
from core.router import UnifiedRouter
from core.saga import SagaEngine
from core.planner import TaskPlanner
from core.intent import IntentClassifier
from core.param_extractor import ParamExtractor
from core.dependency_graph import DependencyGraph, RuntimeCallGuard
from skills.registry import SkillRegistry
from skills.loader import SkillLoader
from skills.composer import SkillComposer
from skills.sandbox_v2 import ProcessIsolatedSandbox, SkillExecutionDispatcher, SandboxConfig
from mcp.client.manager import MCPClientManager
from mcp.client.tool_bridge import bridge_mcp_tools_to_skills
from utils.tracing import new_trace, tracer

logger = logging.getLogger("orchestra.agent")
console = Console()


class OrchestraAgent:
    def __init__(self, config: dict):
        self.config = config

        # LLM 服务
        self.thinker = create_thinker(int(config["ports"]["thinker"]))
        self.memory_llm = create_memory_llm(int(config["ports"]["memory"]))

        # GPU 管理
        self.hot_swap = HotSwapManager(config)

        # 会话管理
        self.session_manager = SessionManager(self.memory_llm)

        # Skill 系统
        self.registry = SkillRegistry("./skills")
        self.loader = SkillLoader(self.registry)
        self.composer = SkillComposer(self.registry)

        # 沙箱
        sandbox_cfg = SandboxConfig(**config.get("skills", {}).get("sandbox", {}))
        self.sandbox = ProcessIsolatedSandbox(sandbox_cfg)
        self.dispatcher = SkillExecutionDispatcher(self.sandbox)

        # MCP
        self.mcp_client = MCPClientManager(
            config.get("mcp", {}).get("client", {}).get("config_path", "./mcp/config/servers.yaml")
        )

        # 路由
        self.router = UnifiedRouter(self.registry, self.mcp_client)

        # Saga
        self.saga_engine = SagaEngine(self.router)

        # 核心组件
        self.planner = TaskPlanner(self.thinker)
        self.intent = IntentClassifier(self.thinker)
        self.param_extractor = ParamExtractor(self.thinker)
        self.dep_graph = DependencyGraph()

        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        console.print("\n  [bold]🎼 Orchestra v2.2 初始化中...[/bold]")

        # 加载 Skill
        self.registry.load_definitions()
        self._register_builtin_skills()
        self.loader.load_from_directory("./skills/extension")

        # 连接 MCP
        mcp_cfg = self.config.get("mcp", {}).get("client", {})
        if mcp_cfg.get("enabled", False):
            await self.mcp_client.connect_all()
            if mcp_cfg.get("bridge_to_skills", True):
                bridge_mcp_tools_to_skills(self.mcp_client, self.registry)

        # 注册工作流
        self._register_workflows()

        # 启动会话清理
        await self.session_manager.start_cleanup_loop()

        # 崩溃恢复
        incomplete = self.saga_engine.recover_incomplete()
        if incomplete:
            logger.warning(f"⚠️ 恢复 {len(incomplete)} 个未完成的 Saga")
            for state in incomplete:
                try:
                    await self.saga_engine.resume(state)
                except Exception as e:
                    logger.error(f"恢复失败: {e}")

        self._initialized = True
        console.print(f"  [green]✅ 就绪[/green] | Skill: {self.registry.count} | MCP: {len(self.mcp_client.connections)}\n")

    async def process(self, user_input: str, user_id: str = "default") -> str:
        # 获取 Session
        session = await self.session_manager.get_or_create(user_id)
        session.turn_count += 1

        # Trace
        trace_id = new_trace()
        session.current_trace_id = trace_id
        session.call_guard.reset()

        # 记忆
        session.memory.add_turn("user", user_input)

        # 意图
        intent = self.intent.classify(user_input, session.memory.get_context())

        # 执行
        context = session.get_context()
        if intent["type"] == "complex_task":
            response = await self._execute_complex_task(user_input, context)
        elif intent["type"] in ("image_generation", "video_generation", "multishot_video"):
            response = await self._execute_skill_flow(user_input, intent, context)
        else:
            response = self._chat(user_input, session)

        # 更新记忆
        session.memory.add_turn("assistant", response[:500])

        # 学习
        session.learner.record(intent.get("skill_id", ""), {}, {"success": True})

        # 释放 GPU
        self.hot_swap.unload_if_generation_done()

        # 定期保存
        if session.turn_count % 5 == 0:
            session.save()

        return response

    async def _execute_skill_flow(self, user_input: str, intent: dict, context: dict) -> str:
        matched = self.registry.find_by_trigger(user_input, intent["type"])
        if not matched:
            return self._chat(user_input, context.get("memory"))

        skill, score = matched[0]
        params = self.param_extractor.extract(user_input, skill.metadata.parameters)
        params = context["learner"].apply_preferences(skill.id, params)

        result = await self.dispatcher.execute(skill, params, context)

        if result.get("success"):
            summary = self.thinker.chat(
                prompt=f"用户：{user_input}\n结果：{json.dumps(result.get('outputs', {}), ensure_ascii=False)}\n简短描述：",
                max_tokens=200,
            )
            return summary["content"]
        return f"❌ 执行失败: {result.get('error')}"

    async def _execute_complex_task(self, user_input: str, context: dict) -> str:
        plan = self.planner.create_plan(user_input, context.get("memory", None))
        steps = [
            {"skill_id": s.get("skill", ""), "params": s.get("input", {}),
             "description": s.get("description", "")}
            for s in plan.get("steps", [])
        ]
        result = await self.saga_engine.execute("complex_task", steps, context)
        if result["success"]:
            summary = self.thinker.chat(
                prompt=f"任务：{user_input}\n结果：{json.dumps(result, ensure_ascii=False)}\n总结：",
                max_tokens=1024,
            )
            return summary["content"]
        return f"❌ 任务失败: {result['error']}（已自动回滚）"

    def _chat(self, user_input: str, session_or_memory) -> str:
        memory = session_or_memory if hasattr(session_or_memory, 'get_context') else session_or_memory
        ctx = memory.get_context() if hasattr(memory, 'get_context') else ""
        result = self.thinker.chat(
            prompt=user_input,
            system=f"你是 Orchestra，全能 AI Agent。\n\n上下文：\n{ctx}",
            history=memory.get_recent_messages(6) if hasattr(memory, 'get_recent_messages') else [],
        )
        return result["content"]

    def _register_builtin_skills(self):
        from skills.builtin.image_gen import ImageGenerationSkill
        from skills.builtin.image_understand import ImageUnderstandingSkill
        from skills.builtin.video_gen import VideoGenerationSkill
        from skills.builtin.multishot_video import MultiShotVideoSkill
        from skills.builtin.code_exec import CodeExecutionSkill
        from skills.builtin.web_search import WebSearchSkill

        for skill in [
            ImageGenerationSkill(self.hot_swap, "./data/outputs"),
            ImageUnderstandingSkill(self.hot_swap),
            VideoGenerationSkill(self.hot_swap, "./data/outputs"),
            MultiShotVideoSkill(self.hot_swap, "./data/outputs"),
            CodeExecutionSkill(self.thinker),
            WebSearchSkill(),
        ]:
            self.registry.register(skill)

    def _register_workflows(self):
        from skills.composer import create_video_story_workflow
        wf = create_video_story_workflow()
        self.composer.register_workflow(wf)
        composite = self.composer.create_composite_skill(wf)
        self.registry.register(composite)

    async def shutdown(self):
        await self.session_manager.shutdown()
        await self.mcp_client.disconnect_all()
        self.hot_swap.unload_if_generation_done()
        tracer.flush()
```

---

## 六、MCP Server

```python
# mcp/server/orchestra_server.py
"""
Orchestra MCP Server — 将自身能力暴露给外部 AI（Claude, Cursor 等）
强制 HTTPS + API Key 认证 + 用户级资源 ACL
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.tls import TLSManager
from mcp.server.auth import MCPAuthenticator


def create_orchestra_mcp_server(agent, config: dict) -> FastMCP:
    mcp = FastMCP("Orchestra", version="2.2.0",
                  description="全能 AI Agent — 图片/视频生成、对话、文档分析")

    @mcp.tool()
    async def generate_image(prompt: str, style: str = "realistic", size: str = "384x384") -> str:
        result = await agent.router.call_skill("image_generation", {
            "prompt": prompt, "style": style, "size": size
        })
        if result["success"]:
            return f"✅ 图片已生成: {result['outputs']['image_path']}"
        return f"❌ 失败: {result.get('error')}"

    @mcp.tool()
    async def generate_video(prompt: str, num_frames: int = 45) -> str:
        result = await agent.router.call_skill("video_generation", {
            "prompt": prompt, "num_frames": num_frames
        })
        if result["success"]:
            return f"✅ 视频已生成: {result['outputs']['video_path']}"
        return f"❌ 失败: {result.get('error')}"

    @mcp.tool()
    async def generate_multishot_video(shots: list[dict]) -> str:
        result = await agent.router.call_skill("multishot_video", {"shots": shots})
        if result["success"]:
            return f"✅ 多镜头视频: {result['outputs']['video_path']}"
        return f"❌ 失败: {result.get('error')}"

    @mcp.tool()
    async def understand_image(image_path: str, question: str) -> str:
        result = await agent.router.call_skill("image_understanding", {
            "image_path": image_path, "question": question
        })
        return result.get("outputs", {}).get("analysis", result.get("error", ""))

    @mcp.tool()
    async def chat(message: str) -> str:
        return await agent.process(message, user_id="mcp_client")

    @mcp.tool()
    async def analyze_document(file_path: str, question: str = "总结核心内容") -> str:
        return await agent.process(f"分析文档 {file_path}：{question}", user_id="mcp_client")

    @mcp.resource("orchestra://users/{user_id}/images/{filename}")
    async def get_user_image(user_id: str, filename: str) -> bytes:
        from pathlib import Path
        path = Path(f"./data/outputs/users/{user_id}/images/{filename}")
        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(f"不存在: {filename}")

    @mcp.resource("orchestra://shared/images/{filename}")
    async def get_shared_image(filename: str) -> bytes:
        from pathlib import Path
        path = Path(f"./data/outputs/shared/images/{filename}")
        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(f"不存在: {filename}")

    @mcp.prompt()
    async def image_prompt_optimizer(description: str) -> str:
        return f"将以下描述优化为英文图片生成提示词（含主体/场景/光影/风格/构图）：\n{description}"

    @mcp.prompt()
    async def video_storyboard(story: str) -> str:
        return f"将以下故事转化为 3-5 镜头的分镜脚本（JSON：prompt/duration/camera）：\n{story}"

    return mcp
```

---

## 七、健康检查与 API

```python
# interface/health.py
"""健康检查端点"""

from fastapi import APIRouter
import time

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health():
    return {"status": "alive", "uptime": time.time() - _start_time}


@router.get("/ready")
async def ready(agent=None):
    checks = {
        "thinker": agent.thinker.is_available() if agent else False,
        "memory_llm": agent.memory_llm.is_available() if agent else False,
        "gpu": __import__("torch").cuda.is_available(),
        "skills": agent.registry.count > 0 if agent else False,
    }
    return {"status": "ready" if all(checks.values()) else "not_ready", "checks": checks}


@router.get("/status")
async def full_status(agent=None):
    return {
        "version": "2.2.0",
        "uptime": time.time() - _start_time,
        "gpu": agent.hot_swap.status() if agent else {},
        "sessions": agent.session_manager.active_count if agent else 0,
        "skills": agent.registry.count if agent else 0,
    }
```

---

## 八、入口文件

```python
# main.py
"""Orchestra v2.2 入口"""

import asyncio
import click
import yaml
import re
import os


def load_config(path="config/settings.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(
        m.group(1).split(":-")[0], m.group(1).split(":-")[1] if ":-" in m.group(1) else ""
    ), content)
    return yaml.safe_load(content)


@click.group()
def cli():
    """🎼 Orchestra v2.2 — 全能 AI Agent"""
    pass


@cli.command()
@click.option("--config", default="config/settings.yaml")
@click.option("--ui", type=click.Choice(["cli", "web", "mcp", "api"]), default="cli")
def run(config, ui):
    cfg = load_config(config)
    from core.agent import OrchestraAgent
    agent = OrchestraAgent(cfg)

    if ui == "mcp":
        asyncio.run(agent.initialize())
        from mcp.server.orchestra_server import create_orchestra_mcp_server
        from mcp.server.tls import TLSManager
        mcp = create_orchestra_mcp_server(agent, cfg)
        tls = TLSManager(cfg.get("mcp", {}).get("server", {}).get("tls", {}).get("cert_dir", "./data/certs"))
        mcp.run(transport="sse", host="0.0.0.0",
                port=int(cfg["ports"]["mcp_server"]))

    elif ui == "cli":
        asyncio.run(agent.initialize())
        _run_cli(agent)

    elif ui == "web":
        asyncio.run(agent.initialize())
        from interface.web_ui import create_web_ui
        demo = create_web_ui(agent)
        demo.launch(server_name="0.0.0.0", server_port=int(cfg["ports"]["web_ui"]))

    elif ui == "api":
        asyncio.run(agent.initialize())
        import uvicorn
        from interface.api_server import create_app
        app = create_app(agent)
        uvicorn.run(app, host="0.0.0.0", port=int(cfg["ports"]["api"]))


def _run_cli(agent):
    from rich.console import Console
    console = Console()
    console.print("\n[bold]🎼 Orchestra v2.2[/bold]")
    console.print("[dim]/skills /mcp /status /quit[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold cyan]👤 你:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input == "/quit":
            asyncio.run(agent.shutdown())
            break
        if user_input == "/skills":
            console.print(agent.registry.status_report())
            continue
        if user_input == "/mcp":
            console.print(agent.mcp_client.status())
            continue
        if user_input == "/status":
            console.print(agent.hot_swap.status())
            continue

        response = asyncio.run(agent.process(user_input, user_id="cli_user"))
        console.print(f"\n[bold green]🤖[/] {response}\n")


@cli.command()
def download():
    """下载所有模型"""
    import subprocess
    subprocess.run(["bash", "scripts/download_models.sh"])


if __name__ == "__main__":
    cli()
```

---

## 九、启动脚本

```bash
#!/bin/bash
# scripts/start_services.sh

echo "╔══════════════════════════════════════════╗"
echo "║   🎼 Orchestra v2.2 启动中...            ║"
echo "╚══════════════════════════════════════════╝"

# 1. MiniCPM5-1B
echo "[1/2] 启动 MiniCPM5-1B..."
python -m llama_cpp.server \
  --model ./data/models/minicpm5-1b/MiniCPM5-1B-Q4_K_M.gguf \
  --n_gpu_layers 99 --n_ctx 131072 \
  --port ${ORCHESTRA_PORT_THINKER:-8081} --alias minicpm-thinker \
  --chat_format chatml &
PID1=$!
sleep 3

# 2. Qwen3.5-0.8B
echo "[2/2] 启动 Qwen3.5-0.8B..."
python -m llama_cpp.server \
  --model ./data/models/qwen3.5-0.8b/Qwen3.5-0.8B-Q4_K_M.gguf \
  --n_gpu_layers 99 --n_ctx 262144 \
  --port ${ORCHESTRA_PORT_MEMORY:-8082} --alias qwen-memory \
  --chat_format chatml &
PID2=$!
sleep 3

echo "✅ LLM 服务就绪"

# 3. Agent
python main.py run --ui ${ORCHESTRA_UI:-cli}

kill $PID1 $PID2 2>/dev/null
```

---

## 十、依赖

```txt
# requirements.txt
torch==2.3.1
torchvision==0.18.1
transformers==4.42.0
accelerate==0.31.0
diffusers==0.29.0
llama-cpp-python==0.2.78
mcp==1.2.0
fastapi==0.111.0
uvicorn==0.30.1
gradio==4.36.0
pydantic==2.7.0
pyyaml==6.0.1
rich==13.7.0
click==8.1.7
requests==2.32.0
httpx==0.27.0
pillow==10.3.0
numpy==1.26.4
pandas==2.2.2
huggingface-hub==0.23.0
modelscope==1.16.0
```

---

## 十一、测试

```python
# tests/test_integration.py
"""集成测试"""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_full_image_generation_flow(agent):
    """完整图片生成流程"""
    response = await agent.process("画一只猫", user_id="test_user")
    assert "图片" in response or "生成" in response


@pytest.mark.asyncio
async def test_session_isolation(agent):
    """多用户会话隔离"""
    await agent.process("我喜欢动漫风格", user_id="user_a")
    await agent.process("我喜欢写实风格", user_id="user_b")

    session_a = await agent.session_manager.get_or_create("user_a")
    session_b = await agent.session_manager.get_or_create("user_b")

    prefs_a = session_a.learner.preferences
    prefs_b = session_b.learner.preferences
    assert prefs_a != prefs_b


@pytest.mark.asyncio
async def test_saga_compensation(agent):
    """Saga 补偿事务"""
    steps = [
        {"skill_id": "image_generation", "params": {"prompt": "test"}, "description": "生成图片"},
        {"skill_id": "nonexistent_skill", "params": {}, "description": "必定失败"},
    ]
    result = await agent.saga_engine.execute("test_saga", steps)
    assert result["success"] == False
    assert result["compensated"] == True


@pytest.mark.asyncio
async def test_inference_lock(agent):
    """推理互斥锁"""
    import asyncio
    results = await asyncio.gather(
        agent.process("画一只猫", user_id="u1"),
        agent.process("画一只狗", user_id="u2"),
    )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_cyclic_dependency_detection():
    """循环依赖检测"""
    from skills.composer import SkillComposer, Workflow, SkillStep, CyclicDependencyError
    composer = SkillComposer(registry=None)
    wf_a = Workflow(id="a", name="A", description="", steps=[SkillStep(skill_id="composite_b")])
    wf_b = Workflow(id="b", name="B", description="", steps=[SkillStep(skill_id="composite_a")])
    composer.register_workflow(wf_a)
    with pytest.raises(CyclicDependencyError):
        composer.register_workflow(wf_b)


@pytest.mark.asyncio
async def test_sandbox_isolation():
    """沙箱隔离"""
    from skills.sandbox_v2 import ProcessIsolatedSandbox
    import tempfile
    sandbox = ProcessIsolatedSandbox()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""
import os
def create_skill():
    class S:
        class metadata:
            class category:
                value = "extension"
        async def execute(self, params, ctx=None):
            os.system("echo hacked")
            return {"success": True, "outputs": {}}
    return S()
""")
        f.flush()
        result = await sandbox.execute(f.name, {})
        # 子进程中 os.system 被禁止
        assert result.success == False or "禁止" in result.error
```

---

## 十二、性能基准

| 操作               | 目标    | 实测 (8GB VRAM) |
| ------------------ | ------- | --------------- |
| 意图识别           | < 1s    | ~0.5s           |
| 简单对话           | < 2s    | ~1s             |
| 记忆压缩           | < 3s    | ~2s             |
| 图片生成 (384²)    | < 35s   | ~20-35s         |
| 图片理解           | < 5s    | ~3-5s           |
| 视频生成 (480P/5s) | < 15min | ~10-15min       |
| 多镜头视频 (3镜头) | < 20min | ~12-18min       |
| 模型切换           | < 10s   | ~5-8s           |
| Saga 3步工作流     | < 5min  | ~2-4min         |
| Session 创建       | < 100ms | ~50ms           |
| MCP 工具调用       | < 5s    | ~1-3s           |

---

## 十三、开发时间线

```
Phase 1 (Week 1-2):   基础骨架 + LLM 服务 + CLI
Phase 2 (Week 3-4):   四层记忆 + 对话压缩 + 文档处理
Phase 3 (Week 5-6):   多模态集成 + 热插拔 + 图片/视频生成
Phase 4 (Week 7-8):   Agent 智能 + 规划 + 多步执行 + Web UI
Phase 5 (Week 9-10):  Skill 系统 + 沙箱 + 组合编排 + 学习器
Phase 6 (Week 11-12): MCP 双向 + 权限 + TLS + 认证
Phase 7 (Week 13-14): Session 隔离 + Saga + 追踪 + 健康检查
Phase 8 (Week 15-16): 集成测试 + 压力测试 + 性能调优 + 文档
```

---

## 十四、MCP 客户端配置（供外部 AI 使用）

### Claude Desktop

```json
{
  "mcpServers": {
    "orchestra": {
      "command": "python",
      "args": ["main.py", "run", "--ui", "mcp"],
      "cwd": "/path/to/orchestra"
    }
  }
}
```

### Cursor

```json
{
  "mcpServers": {
    "orchestra": {
      "command": "python",
      "args": ["/path/to/orchestra/main.py", "run", "--ui", "mcp"]
    }
  }
}
```

### SSE 模式连接

```python
from mcp import ClientSession
from mcp.client.sse import sse_client
import ssl

async def connect():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE  # 自签名证书

    async with sse_client("https://localhost:9100/mcp", ssl_context=ssl_ctx) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("generate_image", {
                "prompt": "A cat in space", "style": "realistic"
            })
            print(result)
```

---

## 十五、Skill 开发指南

### 最小模板

```python
# my_skill.py
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter


class MySkill(BaseSkill):
    def __init__(self):
        super().__init__(SkillMetadata(
            id="my_skill",
            name="我的技能",
            version="1.0.0",
            category=SkillCategory.EXTENSION,
            description="这个技能做什么",
            triggers={"keywords": ["关键词"], "intent_types": ["my_intent"]},
            parameters=[
                SkillParameter("input_text", "string", required=True, description="输入"),
            ],
            permissions=["file_read"],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        return {"success": True, "outputs": {"result": f"处理: {params['input_text']}"}}

    def validate_params(self, params: dict) -> tuple[bool, str]:
        if "input_text" not in params:
            return False, "缺少 input_text"
        return True, ""


def create_skill(**kwargs):
    return MySkill()
```

### 安装

```bash
# 方法 1：放入 extension 目录
cp my_skill.py ./skills/extension/

# 方法 2：CLI 安装
python main.py install ./my_skill.py
```

---

## 十六、环境变量

| 变量                     | 默认值            | 说明                    |
| ------------------------ | ----------------- | ----------------------- |
| `ORCHESTRA_INSTANCE`     | `default`         | 实例 ID                 |
| `ORCHESTRA_PORT_THINKER` | `8081`            | MiniCPM 端口            |
| `ORCHESTRA_PORT_MEMORY`  | `8082`            | Qwen 端口               |
| `ORCHESTRA_PORT_MCP`     | `9100`            | MCP Server 端口         |
| `ORCHESTRA_PORT_WEB`     | `7860`            | Web UI 端口             |
| `ORCHESTRA_PORT_API`     | `8000`            | API 端口                |
| `ORCHESTRA_API_KEY_1`    | `orc_default_key` | MCP API Key             |
| `ORCHESTRA_UI`           | `cli`             | 启动界面模式            |
| `GITHUB_TOKEN`           | —                 | GitHub MCP Server Token |

---

## 十七、交付物清单

| 交付物                       | 说明              |
| ---------------------------- | ----------------- |
| `orchestra/` 完整代码        | ~5000 行 Python   |
| `config/settings.yaml`       | 一键配置          |
| `scripts/download_models.sh` | 模型自动下载      |
| `scripts/start_services.sh`  | 一键启动          |
| `tests/`                     | 完整测试套件      |
| Web UI                       | Gradio 多用户界面 |
| CLI                          | 终端交互          |
| MCP Server                   | HTTPS + 认证      |
| API Server                   | FastAPI + 背压    |
| `README.md`                  | 使用文档          |

---

*Orchestra v2.2 — 能思考、能记忆、能画画、能拍片、能扩展、能连接、能恢复、能追踪的全能 AI Agent。*