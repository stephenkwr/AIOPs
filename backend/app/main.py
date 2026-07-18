"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.agent import router as agent_router
from app.api.approvals import router as approvals_router
from app.api.chat import router as chat_router
from app.api.demo import router as demo_router
from app.api.documents import router as documents_router
from app.api.eval import router as eval_router
from app.api.health import router as health_router
from app.api.ops import router as ops_router
from app.config import settings
from app.limits import limiter


def create_app() -> FastAPI:
    app = FastAPI(title="AI Operations Copilot", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Per-IP rate limits on the endpoints that spend LLM/embedding quota.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(chat_router)
    app.include_router(agent_router)
    app.include_router(approvals_router)
    app.include_router(ops_router)
    app.include_router(eval_router)
    app.include_router(demo_router)

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {
            "app": "AI Operations Copilot",
            "version": app.version,
            "env": settings.app_env,
        }

    return app


app = create_app()
