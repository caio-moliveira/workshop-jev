"""Eventos das execuções em andamento, em memória, para o SSE.

Quem se inscreve recebe os eventos já emitidos e depois os novos, até o fim.
"""

import asyncio
from collections.abc import AsyncIterator

from app.graph import Event, RunResult


class RunChannel:
    def __init__(self):
        self.events: list[Event] = []
        self.result: RunResult | None = None
        self.error: str | None = None
        self.done = False
        self._changed = asyncio.Condition()

    async def publish(self, event: Event) -> None:
        async with self._changed:
            self.events.append(event)
            self._changed.notify_all()

    async def finish(self, result: RunResult | None = None, error: str | None = None) -> None:
        async with self._changed:
            self.result, self.error, self.done = result, error, True
            self._changed.notify_all()

    async def subscribe(self) -> AsyncIterator[Event]:
        sent = 0
        while True:
            async with self._changed:
                await self._changed.wait_for(lambda seen=sent: len(self.events) > seen or self.done)
                pending, done = self.events[sent:], self.done
            for event in pending:
                yield event
            sent += len(pending)
            if done and sent == len(self.events):
                return


class RunRegistry:
    def __init__(self):
        self.channels: dict[str, RunChannel] = {}
        self._tasks: set[asyncio.Task] = set()

    def open(self, run_id: str) -> RunChannel:
        channel = self.channels[run_id] = RunChannel()
        return channel

    def get(self, run_id: str) -> RunChannel | None:
        return self.channels.get(run_id)

    def spawn(self, coroutine) -> None:
        """Roda em segundo plano, guardando a referência para a task não ser coletada."""
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
