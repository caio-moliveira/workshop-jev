"""Eventos de execuções e lotes em andamento, em memória, para o SSE.

Quem se inscreve recebe os eventos já emitidos e depois os novos, até o fim.
"""

import asyncio
from collections.abc import AsyncIterator

from pydantic import BaseModel


class EventChannel:
    def __init__(self):
        self.events: list[BaseModel] = []  # todo evento tem `type`
        self.result: BaseModel | None = None
        self.extra: dict = {}
        self.error: str | None = None
        self.done = False
        self._changed = asyncio.Condition()

    async def publish(self, event: BaseModel) -> None:
        async with self._changed:
            self.events.append(event)
            self._changed.notify_all()

    async def finish(self, result: BaseModel | None = None, error: str | None = None) -> None:
        async with self._changed:
            self.result, self.error, self.done = result, error, True
            self._changed.notify_all()

    async def subscribe(self) -> AsyncIterator[BaseModel]:
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


class Registry:
    """Canais por id. Um registro para execuções e outro para lotes."""

    def __init__(self):
        self.channels: dict[str, EventChannel] = {}
        self._tasks: set[asyncio.Task] = set()

    def open(self, id: str) -> EventChannel:
        channel = self.channels[id] = EventChannel()
        return channel

    def get(self, id: str) -> EventChannel | None:
        return self.channels.get(id)

    def spawn(self, coroutine) -> None:
        """Roda em segundo plano, guardando a referência para a task não ser coletada."""
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
