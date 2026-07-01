from fastapi import FastAPI
from routers import auth

app = FastAPI(title="LLM Fine Tuner & Agent Tester API")

app.include_router(auth.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}