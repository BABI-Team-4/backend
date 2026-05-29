from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import AppError, success_response
from app.db.connections import (
    analyses_collection,
    chat_messages_collection,
    chat_sessions_collection,
    companies_collection,
    job_roles_collection,
    plans_collection,
    usage_collection,
)
from app.schemas.analysis import AnalysisRequest
from app.services.ai_service import run_analysis

router = APIRouter(tags=["analysis"])


# --- 7-1: Request Analysis ---

@router.post("/chat/sessions/{session_id}/analysis")
async def create_analysis(session_id: str, body: AnalysisRequest, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    session = await chat_sessions_collection.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    if not session:
        raise AppError("SESSION_NOT_FOUND", "채팅 세션을 찾을 수 없습니다.", 404)

    ctx = session.get("context", {})
    if not ctx.get("ready_for_analysis"):
        raise AppError("VALIDATION_ERROR", "분석에 필요한 정보가 부족합니다. 기업, 직무, 자기소개서를 모두 입력해주세요.")

    # Check usage limits
    plan_name = user.get("plan", "free")
    plan = await plans_collection.find_one({"plan": plan_name})
    if plan and plan.get("analysis_limit", -1) != -1:
        usage = await usage_collection.find_one({"user_id": user_id})
        used = usage.get("monthly_analysis_used", 0) if usage else 0
        if used >= plan["analysis_limit"]:
            raise AppError("USAGE_LIMIT_EXCEEDED", "이번 달 분석 횟수를 초과했습니다.")

    now = datetime.now(timezone.utc)
    analysis_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "analysis_type": body.analysis_type,
        "status": "processing",
        "progress": 0,
        "current_step": "분석 시작",
        "result": None,
        "created_at": now,
    }
    result = await analyses_collection.insert_one(analysis_doc)
    analysis_id = str(result.inserted_id)

    # Run analysis (sync in this request for simplicity)
    try:
        company = await companies_collection.find_one({"company_id": ctx["target_company_id"]})
        company_name = company["name"] if company else ""
        job_role = await job_roles_collection.find_one({"job_role_id": ctx["target_job_role_id"]})
        job_role_name = job_role["name"] if job_role else ""

        await analyses_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"progress": 30, "current_step": "AI 분석 중"}},
        )

        analysis_result = await run_analysis(
            draft=ctx["essay_answer"],
            question=ctx["essay_question"],
            company=company_name,
            company_id=ctx["target_company_id"],
            job_role_name=job_role_name,
            job_role_id=ctx["target_job_role_id"],
        )

        await analyses_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "current_step": "분석 완료",
                "result": analysis_result,
            }},
        )

        # Increment usage
        await usage_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"monthly_analysis_used": 1}},
            upsert=True,
        )

    except Exception as e:
        await analyses_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": "failed", "current_step": f"분석 실패: {e}"}},
        )

    return success_response({
        "analysis_id": analysis_id,
        "session_id": session_id,
        "status": "processing",
        "current_step": "분석 시작",
    })


# --- 7-2: Get Analysis Status ---

@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await analyses_collection.find_one({"_id": ObjectId(analysis_id), "user_id": str(user["_id"])})
    if not doc:
        raise AppError("NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404)
    return success_response({
        "analysis_id": analysis_id,
        "session_id": doc["session_id"],
        "status": doc["status"],
        "progress": doc.get("progress", 0),
        "current_step": doc.get("current_step", ""),
    })


# --- 7-3: Get Analysis Result ---

@router.get("/analyses/{analysis_id}/result")
async def get_analysis_result(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await analyses_collection.find_one({"_id": ObjectId(analysis_id), "user_id": str(user["_id"])})
    if not doc:
        raise AppError("NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404)
    if doc["status"] != "completed":
        raise AppError("VALIDATION_ERROR", f"분석이 아직 완료되지 않았습니다. 현재 상태: {doc['status']}")

    result = doc.get("result", {})
    result["analysis_id"] = analysis_id
    result["session_id"] = doc["session_id"]
    return success_response(result)


# --- 7-4: Send Analysis to Chat ---

@router.post("/analyses/{analysis_id}/send-to-chat")
async def send_to_chat(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await analyses_collection.find_one({"_id": ObjectId(analysis_id), "user_id": str(user["_id"])})
    if not doc:
        raise AppError("NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404)
    if doc["status"] != "completed":
        raise AppError("VALIDATION_ERROR", "분석이 완료되지 않았습니다.")

    result = doc.get("result", {})
    scores = result.get("scores", {})
    summary = result.get("summary", {})
    overall = scores.get("overall_fit", "N/A")

    company_name = result.get("target_company", {}).get("name", "")
    job_role_name = result.get("target_job_role", {}).get("name", "")

    content = (
        f"분석 결과, 현재 자기소개서는 {company_name} {job_role_name} 직무와 "
        f"{overall}점 수준으로 적합합니다. "
        f"{summary.get('weakness', '')} "
        f"{summary.get('strategy', '')}"
    )

    session_id = doc["session_id"]
    count = await chat_messages_collection.count_documents({"session_id": session_id})
    msg = {
        "message_id": count + 1,
        "session_id": session_id,
        "role": "assistant",
        "content": content,
        "message_type": "analysis_summary",
        "created_at": datetime.now(timezone.utc),
    }
    await chat_messages_collection.insert_one(msg)

    return success_response({
        "session_id": session_id,
        "assistant_message": {
            "message_id": msg["message_id"],
            "role": "assistant",
            "content": content,
            "message_type": "analysis_summary",
        },
    })
