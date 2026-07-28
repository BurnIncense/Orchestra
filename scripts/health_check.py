#!/usr/bin/env python3
"""
Orchestra v2.2 健康检查脚本
调用 /health 和 /ready 端点，输出检查结果。
"""

import sys
import json
import time
import argparse

try:
    import httpx
except ImportError:
    try:
        import requests as httpx
    except ImportError:
        print("❌ 需要 httpx 或 requests 库")
        print("   pip install httpx")
        sys.exit(1)


def check_health(base_url: str, timeout: float = 5.0) -> dict:
    url = f"{base_url.rstrip('/')}/health"
    try:
        if hasattr(httpx, "get"):
            resp = httpx.get(url, timeout=timeout)
        else:
            resp = httpx.get(url, timeout=timeout)
        if hasattr(resp, "json"):
            data = resp.json()
        else:
            data = json.loads(resp.text)
        return {"status": "ok", "data": data, "url": url}
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


def check_ready(base_url: str, timeout: float = 5.0) -> dict:
    url = f"{base_url.rstrip('/')}/ready"
    try:
        if hasattr(httpx, "get"):
            resp = httpx.get(url, timeout=timeout)
        else:
            resp = httpx.get(url, timeout=timeout)
        if hasattr(resp, "json"):
            data = resp.json()
        else:
            data = json.loads(resp.text)
        return {"status": "ok", "data": data, "url": url}
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


def print_result(name: str, result: dict):
    if result["status"] == "ok":
        data = result["data"]
        status = data.get("status", "unknown")
        color = "✅" if status in ("alive", "ready") else "⚠️"
        print(f"{color} {name}: {status}")
        if "uptime" in data:
            uptime = data["uptime"]
            if uptime < 60:
                print(f"   运行时间: {uptime:.1f}s")
            elif uptime < 3600:
                print(f"   运行时间: {uptime/60:.1f}min")
            else:
                print(f"   运行时间: {uptime/3600:.1f}h")
        if "checks" in data:
            for k, v in data["checks"].items():
                mark = "✅" if v else "❌"
                print(f"   {mark} {k}: {v}")
    else:
        print(f"❌ {name}: 连接失败")
        print(f"   URL: {result['url']}")
        print(f"   错误: {result['error']}")


def main():
    parser = argparse.ArgumentParser(description="Orchestra 健康检查")
    parser.add_argument("--host", default="localhost", help="API 主机 (默认: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="API 端口 (默认: 8000)")
    parser.add_argument("--timeout", type=float, default=5.0, help="超时时间 (默认: 5s)")
    parser.add_argument("--watch", action="store_true", help="持续监控模式")
    parser.add_argument("--interval", type=float, default=10.0, help="监控间隔 (默认: 10s)")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    if args.watch:
        print(f"🔍 持续监控 {base_url} (Ctrl+C 退出)")
        try:
            while True:
                print(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
                health = check_health(base_url, args.timeout)
                ready = check_ready(base_url, args.timeout)
                print_result("健康检查 (health)", health)
                print_result("就绪检查 (ready)", ready)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n已退出监控模式")
    else:
        health = check_health(base_url, args.timeout)
        ready = check_ready(base_url, args.timeout)

        print_result("健康检查 (health)", health)
        print()
        print_result("就绪检查 (ready)", ready)

        all_ok = health["status"] == "ok" and ready["status"] == "ok"
        if not all_ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
