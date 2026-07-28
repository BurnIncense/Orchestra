#!/usr/bin/env python3
"""
Orchestra v2.2 性能基准测试脚本
测试意图识别、对话、图片生成等性能，输出基准报告。
"""

import sys
import time
import json
import argparse
import statistics
from pathlib import Path


def run_test(name: str, fn, warmup: int = 1, iterations: int = 5):
    print(f"\n⏱️  测试: {name}")

    for _ in range(warmup):
        try:
            fn()
        except Exception:
            pass

    durations = []
    for i in range(iterations):
        start = time.time()
        try:
            result = fn()
            elapsed = time.time() - start
            durations.append(elapsed)
            status = "✅" if (hasattr(result, "get") and result.get("success", True)) else "⚠️"
            print(f"   迭代 {i+1}/{iterations}: {elapsed*1000:.1f}ms {status}")
        except Exception as e:
            elapsed = time.time() - start
            durations.append(elapsed)
            print(f"   迭代 {i+1}/{iterations}: {elapsed*1000:.1f}ms ❌ ({e})")

    if durations:
        return {
            "name": name,
            "iterations": len(durations),
            "avg_ms": statistics.mean(durations) * 1000,
            "min_ms": min(durations) * 1000,
            "max_ms": max(durations) * 1000,
            "median_ms": statistics.median(durations) * 1000,
        }
    return None


def benchmark_intent_classification(agent):
    def test_fn():
        return agent.intent.classify("帮我生成一张猫咪的图片")
    return test_fn


def benchmark_simple_dialogue(agent):
    async def test_fn():
        import asyncio
        return await agent.process("你好，请介绍一下你自己", user_id="bench_user")
    return test_fn


def benchmark_image_generation(agent):
    async def test_fn():
        import asyncio
        return await agent.process("画一只猫在草地上", user_id="bench_user")
    return test_fn


def benchmark_session_creation(session_manager):
    async def test_fn():
        import asyncio
        session = await session_manager.get_or_create(f"bench_{time.time()}")
        return session
    return test_fn


def benchmark_memory_operation(memory_manager):
    def test_fn():
        memory_manager.add_turn("user", f"测试消息 {time.time()}")
        return memory_manager.get_context()
    return test_fn


def print_report(results: list):
    print("\n" + "=" * 60)
    print("📊 Orchestra v2.2 性能基准报告")
    print("=" * 60)

    print(f"{'测试项':<25} {'平均(ms)':>10} {'最小(ms)':>10} {'最大(ms)':>10} {'中位(ms)':>10}")
    print("-" * 60)

    for r in results:
        if r:
            print(
                f"{r['name']:<25} "
                f"{r['avg_ms']:>10.1f} "
                f"{r['min_ms']:>10.1f} "
                f"{r['max_ms']:>10.1f} "
                f"{r['median_ms']:>10.1f}"
            )

    print("=" * 60)


def save_report(results: list, output_path: str):
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "system": sys.platform,
        "python_version": sys.version,
        "results": results,
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 报告已保存至: {path}")


def main():
    parser = argparse.ArgumentParser(description="Orchestra 性能基准测试")
    parser.add_argument("--iterations", type=int, default=5, help="每个测试的迭代次数 (默认: 5)")
    parser.add_argument("--warmup", type=int, default=1, help="预热次数 (默认: 1)")
    parser.add_argument("--output", default="./data/benchmarks/report.json", help="报告输出路径")
    parser.add_argument("--skip-gpu", action="store_true", help="跳过需要 GPU 的测试")
    parser.add_argument("--config", default="config/settings.yaml", help="配置文件路径")
    args = parser.parse_args()

    print("🎼 Orchestra v2.2 性能基准测试")
    print(f"平台: {sys.platform} | Python: {sys.version.split()[0]}")
    print(f"迭代次数: {args.iterations} | 预热: {args.warmup}")

    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from utils.config import load_config
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        sys.exit(1)

    try:
        from core.agent import OrchestraAgent
        import asyncio
        agent = OrchestraAgent(config)
        asyncio.run(agent.initialize())
        print("✅ Agent 初始化完成")
    except Exception as e:
        print(f"⚠️  Agent 初始化失败，将仅运行单元测试: {e}")
        agent = None

    results = []

    if agent and agent.intent:
        try:
            results.append(run_test(
                "意图识别",
                benchmark_intent_classification(agent),
                warmup=args.warmup,
                iterations=args.iterations,
            ))
        except Exception as e:
            print(f"⚠️  意图识别测试失败: {e}")

    if agent and agent.session_manager:
        try:
            import asyncio
            results.append(run_test(
                "Session 创建",
                benchmark_session_creation(agent.session_manager),
                warmup=args.warmup,
                iterations=args.iterations,
            ))
        except Exception as e:
            print(f"⚠️  Session 创建测试失败: {e}")

    if agent:
        try:
            import asyncio
            results.append(run_test(
                "简单对话",
                benchmark_simple_dialogue(agent),
                warmup=args.warmup,
                iterations=max(1, args.iterations // 2),
            ))
        except Exception as e:
            print(f"⚠️  对话测试失败: {e}")

    if agent and not args.skip_gpu:
        try:
            import asyncio
            results.append(run_test(
                "图片生成",
                benchmark_image_generation(agent),
                warmup=0,
                iterations=max(1, args.iterations // 3),
            ))
        except Exception as e:
            print(f"⚠️  图片生成测试失败: {e}")

    if agent and agent.session_manager:
        try:
            session = asyncio.run(agent.session_manager.get_or_create("bench_memory"))
            results.append(run_test(
                "记忆操作",
                benchmark_memory_operation(session.memory),
                warmup=args.warmup,
                iterations=args.iterations,
            ))
        except Exception as e:
            print(f"⚠️  记忆测试失败: {e}")

    print_report([r for r in results if r])

    if results:
        save_report([r for r in results if r], args.output)


if __name__ == "__main__":
    main()
