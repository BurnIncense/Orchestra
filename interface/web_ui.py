"""Gradio Web UI"""

import asyncio
import uuid


def create_web_ui(agent):
    import gradio as gr

    def _process_message(user_message, history, session_id):
        if not session_id:
            session_id = str(uuid.uuid4())
        response = asyncio.run(agent.process(user_message, user_id=session_id))
        if history is None:
            history = []
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})
        return "", history, session_id

    with gr.Blocks(title="🎼 Orchestra v2.2") as demo:
        gr.Markdown("# 🎼 Orchestra v2.2 — 全能 AI Agent")
        gr.Markdown("✅ 本地 llama.cpp 嵌入式引擎已就绪 | Qwen2.5-0.5B")
        session_id = gr.State("")
        chatbot = gr.Chatbot(height=500)
        msg = gr.Textbox(label="输入消息", placeholder="你想说什么？")
        clear = gr.Button("清空对话")

        msg.submit(
            _process_message,
            inputs=[msg, chatbot, session_id],
            outputs=[msg, chatbot, session_id],
        )
        clear.click(lambda: ([], ""), outputs=[chatbot, session_id])

    return demo
