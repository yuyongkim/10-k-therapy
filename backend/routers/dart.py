"""DART dashboard API - aggregator router.

Includes sub-routers for contracts, analytics, and RAG endpoints.
Maintains backward compatibility: `from backend.routers.dart import router`
"""
from fastapi import APIRouter

from .dart_contracts import router as contracts_router
from .dart_analytics import router as analytics_router
from .dart_rag import router as rag_router

router = APIRouter(prefix="/dart", tags=["dart"])

router.include_router(contracts_router)
router.include_router(analytics_router)
router.include_router(rag_router)
