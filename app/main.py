"""FastAPI application entrypoint for AI Evaluation & Regression Testing Platform."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting AI Evaluation & Regression Testing Platform...")
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Database initialization deferred or failed: {e}")
    yield
    logger.info("Shutting down AI Evaluation & Regression Testing Platform.")


app = FastAPI(
    title="AI Evaluation & Regression Testing Platform",
    description="Enterprise LLM Quality Assurance, Ragas Evaluations, and Regression Prevention API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Root"])
def root():
    """Root landing endpoint with system status."""
    return {
        "service": "AI Evaluation & Regression Testing Platform",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_check": "/health",
        "status": "operational",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
