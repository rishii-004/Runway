from contextlib import asynccontextmanager

from fastapi import FastAPI

from forge.api.routes.runs import router as runs_router
from forge.observability.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="Forge", version="0.1.0", lifespan=lifespan)
app.include_router(runs_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
