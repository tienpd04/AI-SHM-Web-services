from fastapi import APIRouter

from .healthcheck import router as health_router
from .inference import router as inference_router

api_router = APIRouter()

api_router.include_router(health_router)

api_router.include_router(inference_router)

__all__ = ["api_router"]

