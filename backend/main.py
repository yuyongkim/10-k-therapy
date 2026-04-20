"""
License Intelligence API
FastAPI backend for SEC/DART license contract data.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import create_tables
from .routers import contracts, stats, comparison, assistant, dart, annotation

app = FastAPI(
    title="License Intelligence API",
    description="SEC & DART license contract analysis and valuation benchmarking",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3007",
        "http://localhost:3400",
        "https://sec.yule.pics",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contracts.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(comparison.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(dart.router, prefix="/api")
app.include_router(annotation.router, prefix="/api")


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/api/health")
def health():
    return {"status": "ok"}
