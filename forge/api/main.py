from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from forge.api.routes.evaluations import router as evals_router
from forge.api.routes.runs import router as runs_router
from forge.observability.logging import setup_logging
from forge.observability.metrics import get_metrics, get_metrics_content_type


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="Forge", version="0.1.0", lifespan=lifespan)
app.include_router(runs_router)
app.include_router(evals_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=get_metrics(), media_type=get_metrics_content_type())
