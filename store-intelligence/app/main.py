"""
Store Intelligence API — FastAPI entrypoint
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from database import engine, Base
from routers import events, metrics, funnel, heatmap, anomalies, health

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup."""
    Base.metadata.create_all(bind=engine)
    logger.info('"Database tables ready"')
    yield


app = FastAPI(
    title="Store Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Structured request logging ────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    start = time.time()
    request.state.trace_id = trace_id

    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            '{"trace_id":"%s","endpoint":"%s","error":"%s"}',
            trace_id, request.url.path, str(exc),
        )
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    latency_ms = round((time.time() - start) * 1000)
    store_id = request.path_params.get("store_id", "-")
    logger.info(
        '{"trace_id":"%s","store_id":"%s","endpoint":"%s","method":"%s",'
        '"status_code":%d,"latency_ms":%d}',
        trace_id, store_id, request.url.path,
        request.method, response.status_code, latency_ms,
    )
    return response


# ── Mount routers ─────────────────────────────────────────────────
app.include_router(events.router)
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)
app.include_router(health.router)
