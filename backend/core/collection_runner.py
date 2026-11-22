"""Bound browser-agent work and keep collection cancellation out of unrelated tasks."""
import asyncio
import logging
import time


async def run_bounded_agent(agent, browser, should_stop=None, *, timeout=480, max_steps=30, on_stop=None):
    task = asyncio.create_task(agent.run(max_steps=max_steps))
    started = time.monotonic()
    try:
        while not task.done():
            if should_stop and should_stop():
                raise asyncio.CancelledError()
            if time.monotonic() - started >= timeout:
                raise TimeoutError("Collection reached its time limit; saved jobs were retained.")
            await asyncio.wait({task}, timeout=0.25)
        return task.result()
    finally:
        if on_stop:
            on_stop()
        agent.stop()
        if not task.done():
            task.cancel()
        cleanup = asyncio.create_task(browser.kill())
        done, pending = await asyncio.wait({task, cleanup}, timeout=5)
        for pending_task in pending:
            pending_task.cancel()
        for finished in done:
            if finished.cancelled():
                continue
            error = finished.exception()
            if error and finished is cleanup:
                logging.getLogger(__name__).warning("Collection browser cleanup: %s", error)
