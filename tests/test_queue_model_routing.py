"""Offline model routing through queue_submit and the real queue worker."""

import asyncio
import json

import pytest


@pytest.mark.parametrize(
    "kind,override,expected",
    [
        ("deep_research", "", "configured-chat-model"),
        ("deep_research", "explicit-model", "explicit-model"),
        ("deep_research_heavy", "", None),
        ("deep_research_heavy", "explicit-pro-model", "explicit-pro-model"),
    ],
)
def test_queued_research_model_routing(monkeypatch, kind, override, expected):
    from gpt2agent import backend, sse, taskqueue
    from gpt2agent.server import build_server

    calls = []

    class Conversation:
        async def deep_research(self, query, **kwargs):
            calls.append(("deep_research", query, kwargs))
            yield {"type": "done", "text": "light report"}

        async def deep_research_heavy(self, query, **kwargs):
            calls.append(("deep_research_heavy", query, kwargs))
            yield {"type": "done", "text": "heavy report"}

    class Queue:
        enabled = True
        pending = None
        worker = None
        result = None
        error = None

        def __init__(self):
            self.completed = asyncio.Event()

        def submit(self, task_kind, payload):
            self.pending = {
                "id": "test-task", "status": "queued",
                "kind": task_kind, "payload": payload,
            }
            return self.pending

        def requeue_stale(self):
            pass

        def claim_next(self):
            self.worker = asyncio.current_task()
            task, self.pending = self.pending, None
            return task

        def complete(self, task_id, result):
            assert task_id == "test-task"
            self.result = result
            self.completed.set()

        def fail(self, task_id, error):
            self.error = error
            self.completed.set()

    monkeypatch.setattr(backend, "BackendClient", lambda: object())
    monkeypatch.setattr(sse, "ConversationClient", lambda _: Conversation())
    mcp = build_server({
        "server": {"host": "127.0.0.1", "port": 9000},
        "models": {"chat": "configured-chat-model", "heavy_dr": "configured-heavy-model"},
    })

    async def run():
        queue = Queue()
        monkeypatch.setattr(taskqueue, "get_queue", lambda: queue)
        try:
            response = await mcp._tool_manager._tools["queue_submit"].fn(
                kind, "research topic", model=override,
                connectors=["connector-test"],
            )
            assert json.loads(response)["task_id"] == "test-task"
            await asyncio.wait_for(queue.completed.wait(), timeout=2)
            assert queue.error is None
            assert queue.result["text"] == (
                "light report" if kind == "deep_research" else "heavy report"
            )
        finally:
            if queue.worker is not None:
                queue.worker.cancel()
                await asyncio.gather(queue.worker, return_exceptions=True)

    asyncio.run(run())
    assert calls == [(kind, "research topic", {
        "model": expected, "connectors": ["connector-test"],
    })]
