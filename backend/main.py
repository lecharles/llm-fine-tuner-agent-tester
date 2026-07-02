from fastapi import FastAPI
from routers import auth, dataset, qa_pair, training_run

app = FastAPI(title="LLM Fine Tuner & Agent Tester API")

app.include_router(auth.router)
app.include_router(dataset.router)
app.include_router(qa_pair.router)
app.include_router(training_run.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}