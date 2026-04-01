"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import upload, sessions, execution, export
from api.websocket import router as ws_router
from config import settings

app = FastAPI(
    title="QA Agent API",
    description="AI-powered QA testing agent backend",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(upload.router)
app.include_router(sessions.router)
app.include_router(execution.router)
app.include_router(export.router)

# WebSocket
app.include_router(ws_router)


@app.get("/health")
async def health():
    from core.llm_client import get_active_provider_info
    return {"status": "ok", "llm": get_active_provider_info()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
