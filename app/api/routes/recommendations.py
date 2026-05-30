from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import AppError, success_response
from app.db.connections import (
    user_essays_collection,
    plans_collection,
    recommendations_collection,
    usage_collection,
)
from app.schemas.recommendation import RecommendationRequest
from app.services.ai_service import run_recommendation

router = APIRouter(tags=["recommendations"])


# --- 8-1: Create Recommendations ---

@router.post("/essays/{session_id}/recommendations")
async def create_recommendations(
    session_id: str, body: RecommendationRequest, user: dict = Depends(get_current_user)
):
    user_id = str(user["_id"])
    session = await user_essays_collection.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    if not session:
        raise AppError("ESSAY_NOT_FOUND", "자소서를 찾을 수 없습니다.", 404)

    ctx = session.get("context", {})
    if not ctx.get("essay_answer"):
        raise AppError("VALIDATION_ERROR", "자기소개서 답변이 필요합니다.")

    # Check usage limits
    plan_name = user.get("plan", "free")
    plan = await plans_collection.find_one({"plan": plan_name})
    if plan and plan.get("recommendation_limit", -1) != -1:
        usage = await usage_collection.find_one({"user_id": user_id})
        used = usage.get("monthly_recommendation_used", 0) if usage else 0
        if used >= plan["recommendation_limit"]:
            raise AppError("USAGE_LIMIT_EXCEEDED", "이번 달 추천 횟수를 초과했습니다.")

    items = await run_recommendation(
        draft=ctx["essay_answer"],
        question=ctx.get("essay_question", ""),
        company=ctx.get("target_company_name", ""),
        limit=body.limit,
    )

    now = datetime.now(timezone.utc)
    rec_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "items": items,
        "created_at": now,
    }
    result = await recommendations_collection.insert_one(rec_doc)

    await usage_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"monthly_recommendation_used": 1}},
        upsert=True,
    )

    return success_response({
        "recommendation_id": str(result.inserted_id),
        "session_id": session_id,
        "items": items,
    })


# --- 8-2: Get Recommendation ---

@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(recommendation_id: str, user: dict = Depends(get_current_user)):
    doc = await recommendations_collection.find_one({
        "_id": ObjectId(recommendation_id),
        "user_id": str(user["_id"]),
    })
    if not doc:
        raise AppError("NOT_FOUND", "추천 결과를 찾을 수 없습니다.", 404)

    return success_response({
        "recommendation_id": recommendation_id,
        "session_id": doc["session_id"],
        "items": doc.get("items", []),
    })
