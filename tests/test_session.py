import pytest
import time
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_session_per_user_isolation():
    pytest.importorskip("core.session")
    from core.session import SessionManager, Session

    memory_llm = MagicMock()
    manager = SessionManager(memory_llm=memory_llm, cleanup_interval=0.1)

    session_a = await manager.get_or_create("user_a")
    session_b = await manager.get_or_create("user_b")

    assert session_a.user_id == "user_a"
    assert session_b.user_id == "user_b"
    assert session_a.session_id != session_b.session_id

    assert session_a.memory is not None
    assert session_b.memory is not None
    assert session_a.memory is not session_b.memory

    assert session_a.learner is not None
    assert session_b.learner is not None
    assert session_a.learner is not session_b.learner

    await manager.shutdown()


@pytest.mark.asyncio
async def test_session_expiry_cleanup():
    pytest.importorskip("core.session")
    from core.session import SessionManager, SessionConfig

    memory_llm = MagicMock()
    manager = SessionManager(
        memory_llm=memory_llm,
        cleanup_interval=0.1
    )

    cfg = SessionConfig(max_idle_seconds=0.1)

    session = await manager.get_or_create("user_expire")
    session.config = cfg

    assert session.is_expired() is False

    time.sleep(0.15)

    assert session.is_expired() is True

    await manager.shutdown()


@pytest.mark.asyncio
async def test_session_persistence():
    pytest.importorskip("core.session")
    from core.session import Session, SessionConfig

    memory_llm = MagicMock()
    cfg = SessionConfig(persist=True)

    session = Session(
        session_id="test_sess",
        user_id="test_user",
        memory_llm=memory_llm,
        config=cfg,
    )

    session.memory.save = MagicMock()
    session.learner._save = MagicMock()

    session.save()

    session.memory.save.assert_called_once()
    session.learner._save.assert_called_once()
