"""公文写作工作室 —— FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import events, projects, workflow

app = FastAPI(title="公文写作工作室", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api")
app.include_router(workflow.router, prefix="/api")
app.include_router(events.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
