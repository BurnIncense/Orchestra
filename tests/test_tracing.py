import pytest
import asyncio


@pytest.mark.asyncio
async def test_trace_new_and_get_id():
    pytest.importorskip("utils.tracing")
    from utils.tracing import new_trace, get_trace_id

    trace_id = new_trace()

    assert trace_id is not None
    assert trace_id.startswith("orc_")
    assert len(trace_id) > 10

    assert get_trace_id() == trace_id


@pytest.mark.asyncio
async def test_span_hierarchy():
    pytest.importorskip("utils.tracing")
    from utils.tracing import new_trace, tracer

    new_trace()

    parent = tracer.start_span("parent_span", module="test")
    child = tracer.start_span("child_span", module="test")

    assert child.parent_span_id == parent.span_id
    assert child.trace_id == parent.trace_id

    tracer.end_span(child)
    tracer.end_span(parent)

    assert parent.duration_ms >= 0
    assert child.duration_ms >= 0


@pytest.mark.asyncio
async def test_trace_id_propagation():
    pytest.importorskip("utils.tracing")
    from utils.tracing import new_trace, get_trace_id

    new_trace()
    original_id = get_trace_id()

    async def nested_coro():
        return get_trace_id()

    result = await nested_coro()
    assert result == original_id

    async def another_coro():
        new_trace()
        return get_trace_id()

    new_id = await another_coro()
    assert new_id != original_id
    assert get_trace_id() == new_id
