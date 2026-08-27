from fastapi import APIRouter

from app.api.routes import categories, health, products, receipts

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(receipts.router)
