from bson import ObjectId
from fastapi import Depends, Header

from app.core.auth import decode_token
from app.core.responses import AppError
from app.db.connections import users_collection


async def get_current_user(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("UNAUTHORIZED", "인증이 필요합니다.", 401)
    token = authorization[7:]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise AppError("UNAUTHORIZED", "유효하지 않은 토큰입니다.", 401)
        user_id = payload["sub"]
    except Exception:
        raise AppError("UNAUTHORIZED", "유효하지 않은 토큰입니다.", 401)

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise AppError("UNAUTHORIZED", "유효하지 않은 사용자 ID입니다.", 401)

    user = await users_collection.find_one({"_id": oid})
    if not user:
        raise AppError("UNAUTHORIZED", "사용자를 찾을 수 없습니다.", 401)
    return user


async def get_optional_user(authorization: str | None = Header(None)) -> dict | None:
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except Exception:
        return None
