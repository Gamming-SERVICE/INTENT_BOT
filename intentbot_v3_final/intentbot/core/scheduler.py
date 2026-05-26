# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Background Scheduler
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
from typing import Callable, Coroutine, Any

from core.logger import get_logger

log = get_logger("scheduler")


class Scheduler:
    """
    Lightweight background-task manager.

    Tasks registered here are started when `start()` is called and
    cancelled cleanly when `stop()` is called.
    """

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._registered: list[tuple[Callable, float]] = []

    def every(self, interval_seconds: float) -> Callable:
        """
        Decorator that registers a coroutine as a repeating background task.

            @scheduler.every(30)
            async def check_reminders():
                ...
        """
        def decorator(func: Callable[[], Coroutine[Any, Any, None]]) -> Callable:
            self._registered.append((func, interval_seconds))
            return func
        return decorator

    def start(self) -> None:
        for func, interval in self._registered:
            task = asyncio.create_task(self._run_loop(func, interval), name=func.__name__)
            self._tasks.append(task)
            log.info("Scheduled task started: %s (every %.0fs)", func.__name__, interval)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        log.info("All scheduled tasks stopped")

    @staticmethod
    async def _run_loop(func: Callable, interval: float) -> None:
        await asyncio.sleep(5)          # short startup delay
        while True:
            try:
                await func()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Error in scheduled task %s: %s", func.__name__, exc)
            await asyncio.sleep(interval)


# ── Global scheduler instance ─────────────────────────────────────────────────
scheduler = Scheduler()
