import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.collection_runner import run_bounded_agent


async def test_completed_agent_is_cleaned_up():
    result = object()
    agent = SimpleNamespace(run=AsyncMock(return_value=result), stop=Mock())
    browser = SimpleNamespace(kill=AsyncMock())
    assert await run_bounded_agent(agent, browser) is result
    browser.kill.assert_awaited_once()
    agent.stop.assert_called_once()


@pytest.mark.parametrize("cancel", [True, False])
async def test_cancel_and_timeout_stop_only_active_agent(cancel):
    waiting = asyncio.Event()
    agent = SimpleNamespace(run=AsyncMock(side_effect=lambda **_: waiting.wait()), stop=Mock())
    # An async mock must await the wait coroutine, rather than return it as a value.
    async def run(**_):
        await waiting.wait()
    agent.run = run
    browser = SimpleNamespace(kill=AsyncMock())
    error = asyncio.CancelledError if cancel else TimeoutError
    with pytest.raises(error):
        await run_bounded_agent(agent, browser, lambda: cancel, timeout=0)
    agent.stop.assert_called_once()
    browser.kill.assert_awaited_once()
