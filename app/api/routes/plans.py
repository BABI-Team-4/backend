from fastapi import APIRouter

from app.core.responses import success_response
from app.db.connections import plans_collection

router = APIRouter(tags=["plans"])


@router.get("/plans")
async def list_plans():
    docs = await plans_collection.find().to_list(20)
    items = [
        {
            "plan": d["plan"],
            "name": d["name"],
            "price": d["price"],
            "analysis_limit": d["analysis_limit"],
            "recommendation_limit": d["recommendation_limit"],
        }
        for d in docs
    ]
    return success_response(items)
