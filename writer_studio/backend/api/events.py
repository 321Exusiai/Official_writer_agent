"""SSE 事件流路由：异步非阻塞推送工作流过程事件。"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .workflow import get_engine

router = APIRouter(tags=["events"])


@router.get("/projects/{pid}/events")
async def stream_events(pid: str):
    eng = get_engine(pid)

    async def gen():
        last_seq = 0
        while True:
            if last_seq < len(eng.events):
                for ev in eng.events[last_seq:]:
                    yield f"data: {ev.model_dump_json()}\n\n"
                last_seq = len(eng.events)
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream")
