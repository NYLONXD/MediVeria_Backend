from fastapi import APIRouter

from app.controllers.auth_controller import router as auth_router
from app.controllers.report_controller import router as report_router
from app.controllers.upload_controller import router as upload_router
from app.controllers.equipment_controller import router as equipment_router, components_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(report_router)
api_router.include_router(upload_router, prefix="/files", tags=["Files"])
api_router.include_router(equipment_router)
api_router.include_router(components_router)