from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="Survey Builder API",
    description="API конструктора опросов и форм",
    version="1.0.0",
)

app.include_router(api_router)


@app.get("/healthz", tags=["Health"])
def health_check():
    return {"status": "ok"}