import pytest
import asyncio


@pytest.mark.asyncio
async def test_inference_lock():
    pytest.importorskip("models.hot_swap")
    from models.hot_swap import HotSwapManager

    config = {"hardware": {"gpu_memory_gb": 8}}
    manager = HotSwapManager(config)

    assert manager._inference_lock is not None
    assert manager._load_lock is not None
    assert manager._inference_lock.locked() is False


@pytest.mark.asyncio
async def test_queue_backpressure():
    pytest.importorskip("models.hot_swap")
    from models.hot_swap import HotSwapManager, RequestPriority

    config = {"hardware": {"gpu_memory_gb": 8}}
    manager = HotSwapManager(config)

    assert manager._request_queue is not None
    assert manager._request_queue.maxsize == HotSwapManager.MAX_QUEUE_SIZE

    while not manager._request_queue.full():
        manager._request_queue.put_nowait(
            (RequestPriority.USER, 0, "test_task")
        )

    result = await manager.run_inference(
        "vision", lambda: {"success": True},
        priority=RequestPriority.USER
    )

    assert result["success"] is False
    assert "繁忙" in result["error"]


@pytest.mark.asyncio
async def test_model_state_transition():
    pytest.importorskip("models.hot_swap")
    from models.hot_swap import HotSwapManager, ModelState

    config = {"hardware": {"gpu_memory_gb": 8}}
    manager = HotSwapManager(config)

    assert "vision" in manager._models
    assert "video" in manager._models
    assert manager._models["vision"].state == ModelState.UNLOADED
    assert manager._models["video"].state == ModelState.UNLOADED
    assert manager.current is None

    status = manager.status()
    assert "current" in status
    assert "models" in status
    assert status["models"]["vision"]["state"] == "unloaded"
