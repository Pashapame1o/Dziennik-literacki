import asyncio

import pytest

from diary.app.generation_registry import GenerationBuffer, create, get


@pytest.mark.asyncio
async def test_append_then_read_from_offset_zero():
    buffer = GenerationBuffer()
    buffer.append("stage", '{"stage": "piszę"}')
    buffer.append("token", '{"text": "Rano "}')

    assert [e.event for e in buffer.events] == ["stage", "token"]


@pytest.mark.asyncio
async def test_waiter_wakes_up_when_new_event_appended():
    buffer = GenerationBuffer()

    async def append_soon():
        await asyncio.sleep(0.01)
        buffer.append("token", '{"text": "x"}')

    task = asyncio.create_task(append_soon())
    await asyncio.wait_for(buffer.wait_for_more(), timeout=1)
    await task

    assert len(buffer.events) == 1


@pytest.mark.asyncio
async def test_resume_from_offset_only_sees_events_after_it():
    buffer = GenerationBuffer()
    buffer.append("stage", "1")
    buffer.append("stage", "2")
    buffer.append("stage", "3")

    replay = [buffer.events[i].data for i in range(1, len(buffer.events))]
    assert replay == ["2", "3"]


def test_mark_finished_sets_finished_flag():
    buffer = GenerationBuffer()
    assert buffer.finished is False
    buffer.mark_finished()
    assert buffer.finished is True


def test_registry_create_and_get_roundtrip():
    buffer = create("test-gen-id")
    assert get("test-gen-id") is buffer
    assert get("unknown-id") is None


@pytest.mark.asyncio
async def test_expired_buffer_is_swept_on_next_create():
    buffer = create("expiring")
    buffer.mark_finished()
    buffer.created_at -= 20 * 60  # simulate 20 minutes ago, past the 15-minute expiry

    create("another-one")  # sweep runs as a side effect of create()

    assert get("expiring") is None
    assert get("another-one") is not None
