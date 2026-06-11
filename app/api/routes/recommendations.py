from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import AppError, success_response
from app.db.connections import (
    advise_results_collection,
    user_essays_collection,
    recommendations_collection,
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
    essay_answer = ctx.get("essay_answer") or ""
    essay_question = ctx.get("essay_question") or ""

    # context에 essay_answer가 없으면 advise_results에서 모아서 사용
    if not essay_answer:
        advise_docs = await advise_results_collection.find(
            {"session_id": session_id}
        ).sort("question_index", 1).to_list(100)
        if advise_docs:
            parts = []
            for d in advise_docs:
                q = d.get("question", "")
                # result 안의 원본 답변 또는 question 텍스트
                r = d.get("result", {})
                original = r.get("original", "") if isinstance(r, dict) else ""
                if q:
                    parts.append(q)
                if original:
                    parts.append(original)
            essay_answer = "\n".join(parts)
            if not essay_question and advise_docs:
                essay_question = advise_docs[0].get("question", "")

    if not essay_answer:
        raise AppError("VALIDATION_ERROR", "자기소개서 답변이 필요합니다.")

    # 유사 자소서 검색은 무료 (크레딧 차감 없음)
    items = await run_recommendation(
        draft=essay_answer,
        question=essay_question,
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
