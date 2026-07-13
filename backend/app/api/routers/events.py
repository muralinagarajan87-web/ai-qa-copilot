from __future__ import annotations

import queue

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from backend.app.core.container import Container
from events.event_bus import WorkflowEvent

router = APIRouter(prefix="/workflows", tags=["events"])


@router.websocket("/{run_id}/events")
async def workflow_events(websocket: WebSocket, run_id: str) -> None:
    """A thin subscriber on the same in-process EventBus the Orchestrator
    publishes to (events/event_bus.py) -- the frontend gets live state
    without polling, via the same event stream the Orchestrator itself
    would use if we swapped in a real broker later.

    Agent execution runs synchronously in FastAPI's threadpool, so events
    arrive on a worker thread; they are handed to this coroutine through a
    thread-safe queue rather than calling websocket.send_json() directly
    from that thread.
    """
    await websocket.accept()
    container: Container = websocket.app.state.container
    inbox: queue.Queue[WorkflowEvent] = queue.Queue()

    def on_event(event: WorkflowEvent) -> None:
        if event.run_id == run_id:
            inbox.put(event)

    container.event_bus.subscribe("*", on_event)
    try:
        while True:
            event = await run_in_threadpool(inbox.get)
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        container.event_bus.unsubscribe("*", on_event)
