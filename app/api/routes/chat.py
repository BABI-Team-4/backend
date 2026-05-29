from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.core.responses import AppError, success_response
from app.db.connections import (
    chat_messages_collection,
    chat_sessions_collection,
    companies_collection,
    job_roles_collection,
)
from app.schemas.chat import (
    CreateSessionRequest,
    SendMessageRequest,
    SubmitEssayRequest,
    UpdateContextRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])


async def _next_message_id(session_id: str) -> int:
    count = await chat_messages_collection.count_documents({"session_id": session_id})
    return count + 1


async def _save_message(session_id: str, role: str, content: str, message_type: str, **extra) -> dict:
    msg_id = await _next_message_id(session_id)
    now = datetime.now(timezone.utc)
    msg = {
        "message_id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "message_type": message_type,
        "created_at": now,
        **extra,
    }
    await chat_messages_collection.insert_one(msg)
    return msg


def _msg_out(msg: dict) -> dict:
    out = {
        "message_id": msg["message_id"],
        "role": msg["role"],
        "content": msg["content"],
        "message_type": msg["message_type"],
    }
    if "required_fields" in msg:
        out["required_fields"] = msg["required_fields"]
    if "actions" in msg:
        out["actions"] = msg["actions"]
    if "created_at" in msg:
        out["created_at"] = msg["created_at"].isoformat() if isinstance(msg["created_at"], datetime) else msg["created_at"]
    return out


async def _get_session(session_id: str, user_id: str) -> dict:
    session = await chat_sessions_collection.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    if not session:
        raise AppError("SESSION_NOT_FOUND", "채팅 세션을 찾을 수 없습니다.", 404)
    return session


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


def _check_ready(ctx: dict) -> bool:
    return bool(
        ctx.get("target_company_id")
        and ctx.get("target_job_role_id")
        and ctx.get("essay_question")
        and ctx.get("essay_answer")
    )


# --- 6-1: Create Session ---

@router.post("/sessions")
async def create_session(body: CreateSessionRequest, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    now = datetime.now(timezone.utc)
    context = _default_context()

    session = {
        "user_id": user_id,
        "title": "",
        "status": "active",
        "context": context,
        "created_at": now,
        "updated_at": now,
    }
    result = await chat_sessions_collection.insert_one(session)
    session_id = str(result.inserted_id)

    assistant_msg = await _save_message(
        session_id, "assistant",
        "좋아요. 먼저 지원하려는 기업과 직무를 알려주세요.",
        "question",
        required_fields=["target_company", "target_job_role"],
    )

    return success_response({
        "session_id": session_id,
        "status": "active",
        "assistant_message": _msg_out(assistant_msg),
        "context": context,
    })


# --- 6-2: List Sessions ---

@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    user_id = str(user["_id"])
    query = {"user_id": user_id}
    total = await chat_sessions_collection.count_documents(query)
    skip = (page - 1) * limit
    docs = await chat_sessions_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)

    items = []
    for s in docs:
        last_msg = await chat_messages_collection.find_one(
            {"session_id": str(s["_id"])}, sort=[("created_at", -1)]
        )
        items.append({
            "session_id": str(s["_id"]),
            "title": s.get("title", ""),
            "status": s["status"],
            "last_message": last_msg["content"] if last_msg else "",
            "created_at": s["created_at"].isoformat() if isinstance(s["created_at"], datetime) else s["created_at"],
            "updated_at": s["updated_at"].isoformat() if isinstance(s["updated_at"], datetime) else s["updated_at"],
        })

    return success_response({"items": items, "page": page, "limit": limit, "total": total})


# --- 6-3: Get Session Detail ---

@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await _get_session(session_id, str(user["_id"]))
    messages = await chat_messages_collection.find(
        {"session_id": session_id}
    ).sort("created_at", 1).to_list(1000)

    resolved_ctx = await _resolve_context(session.get("context", _default_context()))

    return success_response({
        "session_id": session_id,
        "title": session.get("title", ""),
        "status": session["status"],
        "context": resolved_ctx,
        "messages": [_msg_out(m) for m in messages],
    })


# --- 6-4: Send Message ---

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageRequest, user: dict = Depends(get_current_user)):
    if not body.content.strip():
        raise AppError("MESSAGE_EMPTY", "메시지 내용이 비어있습니다.")

    session = await _get_session(session_id, str(user["_id"]))
    ctx = session.get("context", _default_context())

    user_msg = await _save_message(session_id, "user", body.content, body.message_type)

    # Determine next step based on context
    if not ctx.get("target_company_id") or not ctx.get("target_job_role_id"):
        assistant_content = "좋아요. 이제 자기소개서 문항과 작성한 답변을 보내주세요."
        assistant_type = "question"
        required_fields = ["essay_question", "essay_answer"]
    elif not ctx.get("essay_question") or not ctx.get("essay_answer"):
        assistant_content = "자기소개서 문항과 답변을 보내주세요. 또는 왼쪽 입력창에 직접 입력해도 됩니다."
        assistant_type = "question"
        required_fields = ["essay_question", "essay_answer"]
    else:
        assistant_content = "이제 분석할 수 있어요. AI 분석을 시작할까요?"
        assistant_type = "action_prompt"
        required_fields = []

    assistant_msg = await _save_message(
        session_id, "assistant", assistant_content, assistant_type,
        **({"required_fields": required_fields} if required_fields else {}),
    )

    await chat_sessions_collection.update_one(
        {"_id": session["_id"]},
        {"$set": {"updated_at": datetime.now(timezone.utc)}},
    )

    resolved_ctx = await _resolve_context(ctx)
    return success_response({
        "user_message": _msg_out(user_msg),
        "assistant_message": _msg_out(assistant_msg),
        "context": resolved_ctx,
        "available_actions": [],
    })


# --- 6-5: Submit Essay ---

@router.post("/sessions/{session_id}/essay")
async def submit_essay(session_id: str, body: SubmitEssayRequest, user: dict = Depends(get_current_user)):
    session = await _get_session(session_id, str(user["_id"]))
    ctx = session.get("context", _default_context())

    ctx["essay_question"] = body.essay_question
    ctx["essay_answer"] = body.essay_answer
    ctx["ready_for_analysis"] = _check_ready(ctx)

    await chat_sessions_collection.update_one(
        {"_id": session["_id"]},
        {"$set": {"context": ctx, "updated_at": datetime.now(timezone.utc)}},
    )

    assistant_msg = await _save_message(
        session_id, "assistant",
        "이제 분석할 수 있어요. 기업 Fit 분석을 진행해볼까요?",
        "action_prompt",
        actions=[{"type": "start_analysis", "label": "AI 분석 시작"}],
    )

    return success_response({
        "session_id": session_id,
        "essay": {"essay_question": body.essay_question, "essay_answer": body.essay_answer},
        "context": ctx,
        "assistant_message": _msg_out(assistant_msg),
    })


# --- 6-6: Update Context ---

@router.patch("/sessions/{session_id}/context")
async def update_context(session_id: str, body: UpdateContextRequest, user: dict = Depends(get_current_user)):
    session = await _get_session(session_id, str(user["_id"]))
    ctx = session.get("context", _default_context())

    if body.target_company_id is not None:
        ctx["target_company_id"] = body.target_company_id
    if body.target_job_role_id is not None:
        ctx["target_job_role_id"] = body.target_job_role_id
    if body.job_posting_id is not None:
        ctx["job_posting_id"] = body.job_posting_id
    ctx["ready_for_analysis"] = _check_ready(ctx)

    # Auto-generate title
    resolved = await _resolve_context(ctx)
    company_name = resolved.get("target_company_name", "")
    role_name = resolved.get("target_job_role_name", "")
    if company_name and role_name:
        title = f"{company_name} {role_name} 자기소개서 상담"
        await chat_sessions_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {"context": ctx, "title": title, "updated_at": datetime.now(timezone.utc)}},
        )
    else:
        await chat_sessions_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {"context": ctx, "updated_at": datetime.now(timezone.utc)}},
        )

    return success_response({
        "session_id": session_id,
        "context": resolved,
    })


# --- 6-7: Close Session ---

@router.patch("/sessions/{session_id}/close")
async def close_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await _get_session(session_id, str(user["_id"]))
    await chat_sessions_collection.update_one(
        {"_id": session["_id"]},
        {"$set": {"status": "closed", "updated_at": datetime.now(timezone.utc)}},
    )
    return success_response({"session_id": session_id, "status": "closed"})
