"""Focused tests for headphones transfer route threading behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from music_ferry.web.routes import api


class _DummyLoop:
    def __init__(self):
        self.calls: list[tuple[object | None, object, tuple[object, ...]]] = []

    async def run_in_executor(self, executor, func, *args):
        self.calls.append((executor, func, args))
        return func(*args)


@pytest.mark.asyncio
async def test_transfer_endpoint_runs_work_in_executor(monkeypatch):
    class FakeHeadphonesService:
        def __init__(self, config):
            self.config = config

        def transfer_to_mount(self, mount_path: str | None, source: str):
            return {"ok": True, "mount_path": mount_path, "source": source}

    loop = _DummyLoop()
    monkeypatch.setattr(api, "HeadphonesService", FakeHeadphonesService)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=object())))
    payload = api.HeadphonesTransferRequest(
        mount_path="/tmp/headphones",
        source="spotify",
    )

    result = await api.transfer_to_headphones(payload, request)

    assert result["ok"] is True
    assert result["mount_path"] == "/tmp/headphones"
    assert result["source"] == "spotify"
    assert len(loop.calls) == 1
    assert loop.calls[0][0] is None
