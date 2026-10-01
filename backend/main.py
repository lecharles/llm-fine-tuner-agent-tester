from contextlib import asynccontextmanager

from fastapi import FastAPI
from routers import auth, dataset, qa_pair, training_run, generation, chat, fine_tuned_model, status
from static_serve import mount_spa
from core import bind_guard


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # S15 (#17): LOCAL_MODE=true on a non-loopback bind refuses startup.
    bind_guard.ensure_local_mode_bind_ok()
    yield


# S16 (#18): version is surfaced here (FastAPI/openapi.json -> /docs) and in
# the CLI (`llmtuner --version`); keep in lockstep with the v0.1.0 git tag.
app = FastAPI(
    title="LLM Fine Tuner & Agent Tester API",
    version="0.1.0",
    lifespan=lifespan,
)

bind_guard.register(app)

app.include_router(auth.router)
app.include_router(status.router)
app.include_router(dataset.router)
app.include_router(qa_pair.router)
app.include_router(training_run.router)
app.include_router(generation.router)
app.include_router(generation.status_router)
app.include_router(chat.router)
app.include_router(chat.picker_router)
app.include_router(fine_tuned_model.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Registered last: the SPA catch-all only sees what the routes above do not.
mount_spa(app)