# scripts/download_models.ps1
# Orchestra v2.2 模型下载脚本 (Windows PowerShell)

param(
    [switch]$UseModelScope = $false
)

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🎼 Orchestra v2.2 模型下载中...         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan

$MODEL_DIR = ".\data\models"
New-Item -ItemType Directory -Force -Path $MODEL_DIR | Out-Null

function Download-WithHuggingFace {
    param(
        [string]$RepoId,
        [string]$Filename,
        [string]$TargetDir
    )

    Write-Host "⬇️  下载: $RepoId/$Filename" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    try {
        huggingface-cli download $RepoId $Filename --local-dir $TargetDir --local-dir-use-symlinks False
    } catch {
        python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='$RepoId', filename='$Filename', local_dir='$TargetDir')"
    }
}

function Download-WithModelScope {
    param(
        [string]$ModelId,
        [string]$TargetDir
    )

    Write-Host "⬇️  ModelScope 下载: $ModelId" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    python -c "from modelscope import snapshot_download; snapshot_download('$ModelId', cache_dir='$TargetDir')"
}

Write-Host ""
Write-Host "[1/4] 下载 MiniCPM5-1B (思考者)..." -ForegroundColor Green
$MINICPM_DIR = Join-Path $MODEL_DIR "minicpm5-1b"
if ($UseModelScope) {
    Download-WithModelScope -ModelId "openbmb/MiniCPM5-1B" -TargetDir $MINICPM_DIR
} else {
    Download-WithHuggingFace -RepoId "openbmb/MiniCPM5-1B" -Filename "MiniCPM5-1B-Q4_K_M.gguf" -TargetDir $MINICPM_DIR
}

Write-Host ""
Write-Host "[2/4] 下载 Qwen3.5-0.8B (记忆员)..." -ForegroundColor Green
$QWEN_DIR = Join-Path $MODEL_DIR "qwen3.5-0.8b"
if ($UseModelScope) {
    Download-WithModelScope -ModelId "Qwen/Qwen3.5-0.8B-Instruct" -TargetDir $QWEN_DIR
} else {
    Download-WithHuggingFace -RepoId "Qwen/Qwen3.5-0.8B-Instruct-GGUF" -Filename "Qwen3.5-0.8B-Q4_K_M.gguf" -TargetDir $QWEN_DIR
}

Write-Host ""
Write-Host "[3/4] 下载 Janus-Pro-1B (画师)..." -ForegroundColor Green
$JANUS_DIR = Join-Path $MODEL_DIR "janus-pro-1b"
if ($UseModelScope) {
    Download-WithModelScope -ModelId "deepseek-ai/Janus-Pro-1B" -TargetDir $JANUS_DIR
} else {
    New-Item -ItemType Directory -Force -Path $JANUS_DIR | Out-Null
    python -c "from huggingface_hub import snapshot_download; snapshot_download('deepseek-ai/Janus-Pro-1B', local_dir='$JANUS_DIR')"
}

Write-Host ""
Write-Host "[4/4] 下载 MultiShotMaster (Wan 1.3B, 导演)..." -ForegroundColor Green
$WAN_DIR = Join-Path $MODEL_DIR "wan2.1-1.3b"
if ($UseModelScope) {
    Download-WithModelScope -ModelId "Wan-AI/Wan2.1-T2V-1.3B" -TargetDir $WAN_DIR
} else {
    New-Item -ItemType Directory -Force -Path $WAN_DIR | Out-Null
    python -c "from huggingface_hub import snapshot_download; snapshot_download('Wan-AI/Wan2.1-T2V-1.3B', local_dir='$WAN_DIR')"
}

Write-Host ""
Write-Host "✅ 所有模型下载完成！" -ForegroundColor Green
Write-Host "📁 模型目录: $MODEL_DIR" -ForegroundColor White
Get-ChildItem -Path $MODEL_DIR
