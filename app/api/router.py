from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.companies import router as companies_router
from app.api.routes.chat import router as chat_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.plans import router as plans_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(companies_router)
api_router.include_router(chat_router)
api_router.include_router(analysis_router)
api_router.include_router(recommendations_router)
api_router.include_router(plans_router)
