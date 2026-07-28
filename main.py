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
