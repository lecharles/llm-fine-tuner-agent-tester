from fastapi import FastAPI

app = FastAPI(title="LLM Fine Tuner & Agent Tester API")


@app.get("/health")
def health_check():
    return {"status": "ok"}