from fastapi import APIRouter
from .endpoints import state, assets, inference

api_router = APIRouter()

# 개별 하위 도메인 엔드포인트 연동
api_router.include_router(state.router)
api_router.include_router(assets.router)
api_router.include_router(inference.router)
