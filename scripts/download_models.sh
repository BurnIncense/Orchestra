#!/bin/bash
# scripts/download_models.sh
# Orchestra v2.2 模型下载脚本

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   🎼 Orchestra v2.2 模型下载中...         ║"
echo "╚══════════════════════════════════════════╝"

MODEL_DIR="./data/models"
mkdir -p "$MODEL_DIR"

USE_MODELSCOPE=${USE_MODELSCOPE:-false}

download_with_huggingface() {
    local repo_id="$1"
    local filename="$2"
    local target_dir="$3"

    echo "⬇️  下载: $repo_id/$filename"
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download "$repo_id" "$filename" --local-dir "$target_dir" --local-dir-use-symlinks False
    else
        python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='$repo_id', filename='$filename', local_dir='$target_dir')"
    fi
}

download_with_modelscope() {
    local model_id="$1"
    local target_dir="$2"

    echo "⬇️  ModelScope 下载: $model_id"
    python -c "from modelscope import snapshot_download; snapshot_download('$model_id', cache_dir='$target_dir')"
}

echo ""
echo "[1/4] 下载 MiniCPM5-1B (思考者)..."
MINICPM_DIR="$MODEL_DIR/minicpm5-1b"
mkdir -p "$MINICPM_DIR"
if [ "$USE_MODELSCOPE" = true ]; then
    download_with_modelscope "openbmb/MiniCPM5-1B" "$MINICPM_DIR"
else
    download_with_huggingface "openbmb/MiniCPM5-1B" "MiniCPM5-1B-Q4_K_M.gguf" "$MINICPM_DIR"
fi

echo ""
echo "[2/4] 下载 Qwen3.5-0.8B (记忆员)..."
QWEN_DIR="$MODEL_DIR/qwen3.5-0.8b"
mkdir -p "$QWEN_DIR"
if [ "$USE_MODELSCOPE" = true ]; then
    download_with_modelscope "Qwen/Qwen3.5-0.8B-Instruct" "$QWEN_DIR"
else
    download_with_huggingface "Qwen/Qwen3.5-0.8B-Instruct-GGUF" "Qwen3.5-0.8B-Q4_K_M.gguf" "$QWEN_DIR"
fi

echo ""
echo "[3/4] 下载 Janus-Pro-1B (画师)..."
JANUS_DIR="$MODEL_DIR/janus-pro-1b"
mkdir -p "$JANUS_DIR"
if [ "$USE_MODELSCOPE" = true ]; then
    download_with_modelscope "deepseek-ai/Janus-Pro-1B" "$JANUS_DIR"
else
    python -c "from huggingface_hub import snapshot_download; snapshot_download('deepseek-ai/Janus-Pro-1B', local_dir='$JANUS_DIR')"
fi

echo ""
echo "[4/4] 下载 MultiShotMaster (Wan 1.3B, 导演)..."
WAN_DIR="$MODEL_DIR/wan2.1-1.3b"
mkdir -p "$WAN_DIR"
if [ "$USE_MODELSCOPE" = true ]; then
    download_with_modelscope "Wan-AI/Wan2.1-T2V-1.3B" "$WAN_DIR"
else
    python -c "from huggingface_hub import snapshot_download; snapshot_download('Wan-AI/Wan2.1-T2V-1.3B', local_dir='$WAN_DIR')"
fi

echo ""
echo "✅ 所有模型下载完成！"
echo "📁 模型目录: $MODEL_DIR"
ls -la "$MODEL_DIR"
