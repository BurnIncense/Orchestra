"""CLI 交互逻辑"""

import asyncio


def run_cli(agent):
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
