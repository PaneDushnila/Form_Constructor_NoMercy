from fastapi import APIRouter

from app.api.forms import router as forms_router
from app.api.public import router as public_router
from app.api.results import router as results_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(forms_router)
api_router.include_router(public_router)
api_router.include_router(results_router)