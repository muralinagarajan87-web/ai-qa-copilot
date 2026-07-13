from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger("event_bus")

EventHandler = Callable[["WorkflowEvent"], None]


class WorkflowEvent(BaseModel):
    type: str
    run_id: str
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventBusProtocol(Protocol):
    def publish(self, event: WorkflowEvent) -> None: ...
    def subscribe(self, event_type: str, handler: EventHandler) -> None: ...
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None: ...


class InProcessEventBus:
    """Synchronous, in-process pub/sub. `publish()` invokes handlers
    immediately, so today's behavior is identical to a direct method call --
    the point of introducing this now is that agents and the Orchestrator
    communicate by named event, not by direct reference, so swapping this
    file's internals for a real broker (Redis pub/sub, etc.) later touches
    nothing else. Subscribe to "*" to receive every event (used by the
    workflow-events websocket).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def publish(self, event: WorkflowEvent) -> None:
        logger.info("event run_id=%s type=%s", event.run_id, event.type)
        for handler in list(self._handlers.get(event.type, [])):
            handler(event)
        if event.type != "*":
            for handler in list(self._handlers.get("*", [])):
                handler(event)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type)
        if handlers and handler in handlers:
            handlers.remove(handler)
