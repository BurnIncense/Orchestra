"""FastAPI 服务"""

import asyncio
import threading


def create_app(agent):
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from interface.health import router as health_router

    app = FastAPI(title="Orchestra v2.2 API", version="2.2.0")

    _concurrent_lock = threading.Semaphore(10)

    @app.middleware("http")
    async def backpressure_middleware(request, call_next):
        if not _concurrent_lock.acquire(blocking=False):
            raise HTTPException(status_code=503, detail="服务器繁忙，请稍后再试")
        try:
            response = await call_next(request)
            return response
        finally:
            _concurrent_lock.release()

    app.include_router(health_router)

    class ChatRequest(BaseModel):
        message: str
        user_id: str = "default"

    class ChatResponse(BaseModel):
        response: str

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        try:
            result = await agent.process(request.message, user_id=request.user_id)
            return ChatResponse(response=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app
