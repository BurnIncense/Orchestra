import pytest
import tempfile
import pickle
from pathlib import Path


@pytest.mark.asyncio
async def test_memory_add_turn_and_get_context():
    pytest.importorskip("memory.manager")
    from memory.manager import MemoryManager

    manager = MemoryManager(config={"max_working_turns": 5, "auto_save_interval": 0})

    manager.add_turn("user", "你好")
    manager.add_turn("assistant", "你好！有什么可以帮你？")
    manager.add_turn("user", "今天天气怎么样？")

    assert manager.turn_count == 3
    assert len(manager.working_memory) == 3

    context = manager.get_context()
    assert "你好" in context
    assert "今天天气怎么样？" in context


@pytest.mark.asyncio
async def test_memory_persistence_save_load():
    pytest.importorskip("memory.manager")
    from memory.manager import MemoryManager

    with tempfile.TemporaryDirectory() as tmpdir:
        persist_path = str(Path(tmpdir) / "memory.pkl")

        manager1 = MemoryManager(config={
            "max_working_turns": 10,
            "persist_path": persist_path,
            "auto_save_interval": 0,
        })

        manager1.add_turn("user", "我喜欢蓝色")
        manager1.add_turn("assistant", "好的，已记录")
        manager1.preferences["color"] = "blue"

        manager1.save()

        manager2 = MemoryManager(config={
            "max_working_turns": 10,
            "persist_path": persist_path,
            "auto_save_interval": 0,
        })

        assert manager2.turn_count == 2
        assert len(manager2.working_memory) == 2
        assert manager2.preferences.get("color") == "blue"


@pytest.mark.asyncio
async def test_memory_get_recent_messages():
    pytest.importorskip("memory.manager")
    from memory.manager import MemoryManager

    manager = MemoryManager(config={"max_working_turns": 20, "auto_save_interval": 0})

    for i in range(10):
        manager.add_turn("user", f"消息 {i}")
        manager.add_turn("assistant", f"回复 {i}")

    recent = manager.get_recent_messages(n=6)

    assert len(recent) == 6
    assert recent[-1]["role"] == "assistant"
    assert "回复 9" in recent[-1]["content"]
