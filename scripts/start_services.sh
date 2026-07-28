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
