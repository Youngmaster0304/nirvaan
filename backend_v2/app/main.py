from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.config import settings
from app.database import init_db, DB_TYPE
from app.api.indian_routes import router as indian_router

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR / "frontend_v2"

_index_html = ""
if (FRONTEND_DIR / "index.html").exists():
    _index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Niravaan RailVision",
    description="AI-Powered Block Planning for Indian Railways",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(indian_router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def root():
    if _index_html:
        return HTMLResponse(content=_index_html)
    return HTMLResponse(content="<h1>Niravaan RailVision v2.0</h1><p><a href='/docs'>API Docs</a></p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
