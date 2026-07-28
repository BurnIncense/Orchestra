# 🎼 Orchestra v2.2

> 本地运行、完全离线、零成本的全能 AI Agent 平台

Orchestra 是一个融合四个开源模型，通过 Skill 技能系统和 MCP 协议实现无限能力扩展的全能 AI Agent。它能思考、能记忆、能画画、能拍片、能扩展、能连接、能恢复、能追踪。

---

## 模型矩阵

| 角色     | 模型                       | 职责                                          | 显存占用         |
| -------- | -------------------------- | --------------------------------------------- | ---------------- |
| 🧮 思考者 | MiniCPM5-1B (Q4_K_M)       | 推理、代码、规划、工具调用、Agent 决策        | 0.7 GB（常驻）   |
| 📚 记忆员 | Qwen3.5-0.8B (Q4_K_M)      | 262K 上下文管理、对话压缩、文档理解、偏好学习 | 0.5 GB（常驻）   |
| 🎨 画师   | Janus-Pro-1B               | 文生图、图片理解、图片编辑                    | 4.0 GB（热插拔） |
| 🎬 导演   | MultiShotMaster (Wan 1.3B) | 多镜头叙事视频、镜头调度、图生视频            | 6.0 GB（热插拔） |

```
┌─────────────────────── 8 GB GPU ───────────────────────┐
│                                                         │
│  [常驻区 1.2GB]          [热插拔区 6.8GB]               │
│  ┌──────────────┐       ┌─────────────────────────┐    │
│  │ MiniCPM5-1B  │       │  模式A: Janus-Pro  4GB  │    │
│  │ Q4_K_M 0.7G │       │  模式B: MultiShot  6GB  │    │
│  ├──────────────┤       │                         │    │
│  │ Qwen3.5-0.8B│       │  ⚠️ A/B 互斥           │    │
│  │ Q4_K_M 0.5G │       └─────────────────────────┘    │
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 硬件要求

| 资源     | 最低  | 推荐  |
| -------- | ----- | ----- |
| GPU 显存 | 8 GB  | 12 GB |
| 系统内存 | 16 GB | 32 GB |
| 磁盘     | 30 GB | 50 GB |
| CUDA     | 12.1+ | 12.4+ |

---

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd Orchestra
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 下载模型

**Linux / macOS (bash):**

```bash
bash scripts/download_models.sh

# 使用 ModelScope (国内推荐):
USE_MODELSCOPE=true bash scripts/download_models.sh
```

**Windows (PowerShell):**

```powershell
.\scripts\download_models.ps1

# 使用 ModelScope (国内推荐):
.\scripts\download_models.ps1 -UseModelScope
```

或者通过 CLI：

```bash
python main.py download
```

---

## 使用方法

### CLI 模式（命令行交互）

```bash
# 先启动 LLM 服务
bash scripts/start_services.sh

# 或直接运行
python main.py run --ui cli
```

支持命令：
- `/skills` - 查看已加载的 Skill
- `/mcp` - 查看 MCP 连接状态
- `/status` - 查看系统状态
- `/quit` - 退出

### Web 模式（Gradio 界面）

```bash
python main.py run --ui web
```

浏览器访问：http://localhost:7860

### MCP 模式（Model Context Protocol 服务）

```bash
python main.py run --ui mcp
```

- MCP Server: https://localhost:9100/mcp
- 支持 SSE 传输
- TLS 加密 + API Key 认证

**Claude Desktop 配置：**

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

### API 模式（FastAPI 服务）

```bash
python main.py run --ui api
```

- API 地址: http://localhost:8000
- 健康检查: http://localhost:8000/health
- 就绪检查: http://localhost:8000/ready
- 系统状态: http://localhost:8000/status

```bash
# 健康检查
python scripts/health_check.py

# 持续监控
python scripts/health_check.py --watch
```

---

## 目录结构

```
orchestra/
├── config/                  # 配置文件
│   ├── settings.yaml        # 全局配置
│   └── tools.yaml           # 工具注册表
│
├── core/                    # 核心模块
│   ├── agent.py             # Agent 主循环
│   ├── session.py           # 会话管理器（Per-User 隔离）
│   ├── router.py            # 统一路由器
│   ├── saga.py              # Saga 补偿事务引擎
│   ├── planner.py           # 任务规划器
│   ├── intent.py            # 意图识别
│   └── executor.py          # 执行引擎
│
├── memory/                  # 记忆系统
│   ├── manager.py           # 四层记忆管理器
│   ├── compressor.py        # 对话压缩
│   ├── document.py          # 文档处理
│   └── persistence.py       # 持久化
│
├── models/                  # 模型服务
│   ├── llm_service.py       # LLM 服务封装
│   ├── hot_swap.py          # GPU 热插拔管理
│   ├── vision_service.py    # 视觉服务（Janus）
│   └── video_service.py     # 视频服务（MultiShot）
│
├── skills/                  # Skill 系统
│   ├── builtin/             # 内置 Skill
│   ├── extension/           # 扩展 Skill（沙箱执行）
│   ├── definitions/         # Skill 定义 (YAML)
│   ├── registry.py          # Skill 注册中心
│   ├── loader.py            # Skill 加载器
│   ├── sandbox_v2.py        # 进程级隔离沙箱
│   └── composer.py          # 组合编排器
│
├── mcp/                     # MCP 协议层
│   ├── client/              # MCP 客户端
│   ├── server/              # MCP 服务端
│   └── config/              # MCP 配置
│
├── interface/               # 用户接口
│   ├── cli.py               # 命令行界面
│   ├── web_ui.py            # Gradio Web 界面
│   ├── api_server.py        # FastAPI 服务
│   └── health.py            # 健康检查端点
│
├── utils/                   # 工具函数
│   ├── tracing.py           # 分布式追踪
│   ├── logger.py            # 结构化日志
│   ├── config.py            # 配置加载
│   └── exceptions.py        # 统一异常
│
├── tests/                   # 测试套件
├── scripts/                 # 脚本工具
├── data/                    # 数据目录（运行时生成）
├── main.py                  # 入口文件
└── requirements.txt         # 依赖清单
```

---

## Skill 开发指南

### 最小 Skill 模板

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


def create_skill(**kwargs):
    return MySkill()
```

### 安装 Skill

```bash
# 方法 1：放入 extension 目录
cp my_skill.py ./skills/extension/

# 方法 2：CLI 安装
python main.py install ./my_skill.py
```

### 完整开发文档

详细的 Skill 开发指南请参阅开发文档 `Orchestra Agent-v2.0.md` 第十五节。

---

## 运行测试

```bash
# 收集所有测试
python -m pytest tests/ --collect-only -q

# 运行单元测试（不需要 GPU）
python -m pytest tests/test_router.py tests/test_saga.py tests/test_memory.py -v

# 运行所有测试（需要完整环境）
python -m pytest tests/ -v

# 性能基准测试
python scripts/benchmark.py
```

---

## 核心设计原则

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

## 环境变量

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

---

*Orchestra v2.2 — 能思考、能记忆、能画画、能拍片、能扩展、能连接、能恢复、能追踪的全能 AI Agent。*
