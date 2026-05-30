from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.core.responses import AppError, success_response
from app.db.connections import (
    advise_results_collection,
    companies_collection,
    job_roles_collection,
    user_essays_collection,
)
from app.schemas.essay_session import (
    CreateEssayRequest,
    SubmitEssayRequest,
)

router = APIRouter(prefix="/essays", tags=["essays"])


def _isoformat(dt) -> str:
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


async def _get_essay(essay_id: str, user_id: str) -> dict:
    doc = await user_essays_collection.find_one({"_id": ObjectId(essay_id), "user_id": user_id})
    if not doc:
        raise AppError("ESSAY_NOT_FOUND", "자소서를 찾을 수 없습니다.", 404)
    return doc


async def _resolve_context(ctx: dict) -> dict:
    out = {**ctx}
    if ctx.get("target_company_id"):
        company = await companies_collection.find_one({"company_id": ctx["target_company_id"]})
        out["target_company_name"] = company["name"] if company else ""
    if ctx.get("target_job_role_id"):
        role = await job_roles_collection.find_one({"job_role_id": ctx["target_job_role_id"]})
        out["target_job_role_name"] = role["name"] if role else ""
    return out


def _default_context() -> dict:
    return {
        "target_company_id": None,
        "target_job_role_id": None,
        "job_posting_id": None,
        "essay_question": None,
        "essay_answer": None,
        "ready_for_analysis": False,
    }


# --- Create Essay ---

@router.post("")
async def create_essay(body: CreateEssayRequest, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    now = datetime.now(timezone.utc)
    context = _default_context()

    doc = {
        "user_id": user_id,
        "title": body.title or "",
        "status": "active",
        "context": context,
        "created_at": now,
        "updated_at": now,
    }
    result = await user_essays_collection.insert_one(doc)
    essay_id = str(result.inserted_id)

    return success_response({
        "session_id": essay_id,
        "status": "active",
        "context": context,
    })


# --- List Essays ---

@router.get("")
async def list_essays(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    keyword: str = Query("", alias="keyword"),
    user: dict = Depends(get_current_user),
):
    user_id = str(user["_id"])
    query = {"user_id": user_id}
    term = keyword.strip()
    if term:
        escaped = {"$regex": term, "$options": "i"}
        query["$or"] = [
            {"title": escaped},
            {"context.essay_question": escaped},
            {"context.essay_answer": escaped},
        ]
    total = await user_essays_collection.count_documents(query)
    skip = (page - 1) * limit
    docs = await user_essays_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)

    items = []
    for s in docs:
        sid = str(s["_id"])
        advise_doc = await advise_results_collection.find_one(
            {"session_id": sid}, sort=[("question_index", 1)]
        )
        if advise_doc and advise_doc.get("result"):
            result_data = advise_doc["result"]
            preview = result_data.get("summary", "") or result_data.get("rewrite", "")[:80]
        else:
            preview = ""
        items.append({
            "session_id": sid,
            "title": s.get("title", ""),
            "status": s["status"],
            "last_message": preview,
            "created_at": _isoformat(s["created_at"]),
            "updated_at": _isoformat(s["updated_at"]),
        })

    return success_response({"items": items, "page": page, "limit": limit, "total": total})


# --- Get Essay Detail ---

@router.get("/{essay_id}")
async def get_essay(essay_id: str, user: dict = Depends(get_current_user)):
    doc = await _get_essay(essay_id, str(user["_id"]))
    resolved_ctx = await _resolve_context(doc.get("context", _default_context()))

    return success_response({
        "session_id": essay_id,
        "title": doc.get("title", ""),
        "status": doc["status"],
        "context": resolved_ctx,
        "messages": [],
    })


# --- Submit Essay Content ---

@router.post("/{essay_id}/essay")
async def submit_essay(essay_id: str, body: SubmitEssayRequest, user: dict = Depends(get_current_user)):
    doc = await _get_essay(essay_id, str(user["_id"]))
    ctx = doc.get("context", _default_context())

    ctx["essay_question"] = body.essay_question
    ctx["essay_answer"] = body.essay_answer
    ctx["ready_for_analysis"] = bool(ctx.get("target_company_id") and ctx.get("essay_question") and ctx.get("essay_answer"))

    await user_essays_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"context": ctx, "updated_at": datetime.now(timezone.utc)}},
    )

    return success_response({
        "session_id": essay_id,
        "essay": {"essay_question": body.essay_question, "essay_answer": body.essay_answer},
        "context": ctx,
    })


# --- Rename Essay ---

@router.patch("/{essay_id}/title")
async def rename_essay(essay_id: str, body: dict, user: dict = Depends(get_current_user)):
    doc = await _get_essay(essay_id, str(user["_id"]))
    title = body.get("title", "").strip()
    if not title:
        raise AppError("VALIDATION_ERROR", "제목을 입력해주세요.")
    await user_essays_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"title": title, "updated_at": datetime.now(timezone.utc)}},
    )
    return success_response({"session_id": essay_id, "title": title})


# --- Close Essay ---

@router.patch("/{essay_id}/close")
async def close_essay(essay_id: str, user: dict = Depends(get_current_user)):
    doc = await _get_essay(essay_id, str(user["_id"]))
    await user_essays_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "closed", "updated_at": datetime.now(timezone.utc)}},
    )
    return success_response({"session_id": essay_id, "status": "closed"})


# --- Delete Essay ---

@router.delete("/{essay_id}")
async def delete_essay(essay_id: str, user: dict = Depends(get_current_user)):
    doc = await _get_essay(essay_id, str(user["_id"]))
    await user_essays_collection.delete_one({"_id": doc["_id"]})
    await advise_results_collection.delete_many({"session_id": essay_id})
    return success_response({"session_id": essay_id, "deleted": True})


# --- Save Advise Result ---

@router.post("/{essay_id}/advise-result")
async def save_advise_result(essay_id: str, body: dict, user: dict = Depends(get_current_user)):
    doc = await _get_essay(essay_id, str(user["_id"]))
    now = datetime.now(timezone.utc)
    question_index = body.get("question_index", 0)
    advise_doc = {
        "session_id": essay_id,
        "user_id": str(user["_id"]),
        "question_index": question_index,
        "question": body.get("question", ""),
        "result": body.get("result"),
        "created_at": now,
    }
    await advise_results_collection.replace_one(
        {"session_id": essay_id, "question_index": question_index},
        advise_doc,
        upsert=True,
    )
    await user_essays_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "closed", "updated_at": now}},
    )
    return success_response({"session_id": essay_id, "question_index": question_index})


# --- Get Advise Results ---

@router.get("/{essay_id}/advise-results")
async def get_advise_results(essay_id: str, user: dict = Depends(get_current_user)):
    await _get_essay(essay_id, str(user["_id"]))
    docs = await advise_results_collection.find(
        {"session_id": essay_id}
    ).sort("question_index", 1).to_list(100)
    items = [
        {
            "question_index": d["question_index"],
            "question": d["question"],
            "result": d["result"],
            "created_at": _isoformat(d["created_at"]),
        }
        for d in docs
    ]
    return success_response({"items": items})
