"""快速下载测试模型 — Qwen2.5-0.5B-Instruct GGUF (~350MB)"""
import os
import sys
import urllib.request

MODEL_DIR = "./data/models/qwen2.5-0.5b"
MODEL_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"

def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    target = os.path.join(MODEL_DIR, MODEL_FILE)

    if os.path.exists(target):
        print(f"✅ 模型已存在: {target}")
        print(f"   大小: {os.path.getsize(target) / 1024 / 1024:.1f} MB")
        return 0

    print(f"📥 下载测试模型: Qwen2.5-0.5B-Instruct (GGUF Q4_K_M)")
    print(f"   来源: {MODEL_URL}")
    print(f"   保存到: {os.path.abspath(target)}")
    print()

    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = downloaded * 100 / total_size if total_size else 0
        mb = downloaded / 1024 / 1024
        sys.stdout.write(f"\r   进度: {pct:.1f}% ({mb:.1f} MB)")
        sys.stdout.flush()

    try:
        urllib.request.urlretrieve(MODEL_URL, target, reporthook=progress)
        print()
        print(f"✅ 下载完成！大小: {os.path.getsize(target) / 1024 / 1024:.1f} MB")
        print()
        print("👉 在 config/settings.yaml 中修改 models.thinker.path 为:")
        print(f"   {os.path.abspath(target)}")
        return 0
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
