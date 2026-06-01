import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import bcrypt
import httpx
from fastapi import APIRouter

from app.core.auth import create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.core.responses import AppError, success_response
from app.db.connections import refresh_tokens_collection, usage_collection, users_collection
from app.schemas.auth import LoginRequest, LogoutRequest, OAuthCallbackRequest, RefreshRequest, SignupRequest

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state store (use Redis in production)
_oauth_states: dict[str, dict] = {}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: str, redirect_uri: str):
    state = secrets.token_urlsafe(32)

    if provider == "google":
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    elif provider == "kakao":
        params = {
            "client_id": settings.kakao_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        auth_url = f"{KAKAO_AUTH_URL}?{urlencode(params)}"
    else:
        raise AppError("VALIDATION_ERROR", "지원하지 않는 provider입니다.")

    _oauth_states[state] = {"provider": provider, "redirect_uri": redirect_uri}
    return success_response({
        "provider": provider,
        "authorization_url": auth_url,
        "state": state,
    })


@router.post("/oauth/{provider}/callback")
async def oauth_callback(provider: str, body: OAuthCallbackRequest):
    try:
        user_info = await _exchange_oauth(provider, body.code, body.redirect_uri)
    except Exception as e:
        raise AppError("OAUTH_FAILED", f"OAuth 인증에 실패했습니다: {e}", 401)

    email = user_info["email"]
    # OAuth 사용자는 provider별로 구분하여 조회
    user = await users_collection.find_one({"email": email, "auth_provider": provider})
    if not user:
        # 기존 다른 provider로 가입한 동일 이메일이 있는지 확인
        user = await users_collection.find_one({"email": email})

    now = datetime.now(timezone.utc)
    if not user:
        default_plan = "pro"
        user = {
            "email": email,
            "name": user_info.get("name", ""),
            "profile_image_url": user_info.get("picture", ""),
            "auth_provider": provider,
            "role": "user",
            "plan": default_plan,
            "created_at": now,
        }
        result = await users_collection.insert_one(user)
        user["_id"] = result.inserted_id

        # Initialize usage
        await usage_collection.insert_one({
            "user_id": str(user["_id"]),
            "monthly_analysis_used": 0,
            "monthly_recommendation_used": 0,
            "reset_at": None,
        })

    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    await refresh_tokens_collection.insert_one({
        "user_id": user_id,
        "token": refresh_token,
        "created_at": now,
    })

    return success_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": user_id,
            "email": user["email"],
            "name": user["name"],
            "profile_image_url": user.get("profile_image_url", ""),
            "auth_provider": user["auth_provider"],
            "role": user["role"],
            "plan": user["plan"],
        },
    })


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError()
    except Exception:
        raise AppError("UNAUTHORIZED", "유효하지 않은 refresh token입니다.", 401)

    stored = await refresh_tokens_collection.find_one({"token": body.refresh_token})
    if not stored:
        raise AppError("UNAUTHORIZED", "이미 사용되었거나 만료된 토큰입니다.", 401)

    new_access = create_access_token(payload["sub"])
    return success_response({"access_token": new_access})


@router.post("/logout")
async def logout(body: LogoutRequest):
    await refresh_tokens_collection.delete_one({"token": body.refresh_token})
    return success_response({"logged_out": True})


@router.post("/signup")
async def signup(body: SignupRequest):
    existing = await users_collection.find_one({"email": body.email})
    if existing:
        raise AppError("DUPLICATE_EMAIL", "이미 가입된 이메일입니다.", 409)

    if len(body.password) < 6:
        raise AppError("VALIDATION_ERROR", "비밀번호는 6자 이상이어야 합니다.")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc)
    user = {
        "email": body.email,
        "name": body.name or body.email.split("@")[0],
        "profile_image_url": "",
        "auth_provider": "email",
        "role": "user",
        "plan": "pro",
        "password_hash": hashed,
        "created_at": now,
    }
    result = await users_collection.insert_one(user)
    user["_id"] = result.inserted_id

    await usage_collection.insert_one({
        "user_id": str(user["_id"]),
        "monthly_analysis_used": 0,
        "monthly_recommendation_used": 0,
        "reset_at": None,
    })

    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    await refresh_tokens_collection.insert_one({
        "user_id": user_id,
        "token": refresh_token,
        "created_at": now,
    })

    return success_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": user_id,
            "email": user["email"],
            "name": user["name"],
            "profile_image_url": "",
            "auth_provider": "email",
            "role": user["role"],
            "plan": user["plan"],
        },
    })


@router.post("/login")
async def email_login(body: LoginRequest):
    user = await users_collection.find_one({"email": body.email})
    if not user or not user.get("password_hash"):
        raise AppError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)

    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise AppError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)

    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    now = datetime.now(timezone.utc)
    await refresh_tokens_collection.insert_one({
        "user_id": user_id,
        "token": refresh_token,
        "created_at": now,
    })

    return success_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": user_id,
            "email": user["email"],
            "name": user["name"],
            "profile_image_url": user.get("profile_image_url", ""),
            "auth_provider": user["auth_provider"],
            "role": user["role"],
            "plan": user["plan"],
        },
    })


@router.post("/dev-login")
async def dev_login(body: dict):
    """
    Development-only endpoint. Logs in as a test user without OAuth.
    Request: {"email": "test@example.com"}
    """
    email = body.get("email", "test@example.com")
    user = await users_collection.find_one({"email": email})
    if not user:
        raise AppError("NOT_FOUND", f"테스트 계정 '{email}'을 찾을 수 없습니다. init-mongo.js로 시드해주세요.", 404)

    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    now = datetime.now(timezone.utc)
    await refresh_tokens_collection.insert_one({
        "user_id": user_id,
        "token": refresh_token,
        "created_at": now,
    })

    return success_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": user_id,
            "email": user["email"],
            "name": user["name"],
            "profile_image_url": user.get("profile_image_url", ""),
            "auth_provider": user["auth_provider"],
            "role": user["role"],
            "plan": user["plan"],
        },
    })


async def _exchange_oauth(provider: str, code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient() as client:
        if provider == "google":
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            tokens = resp.json()
            resp2 = await client.get(GOOGLE_USERINFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            return resp2.json()

        elif provider == "kakao":
            resp = await client.post(KAKAO_TOKEN_URL, data={
                "code": code,
                "client_id": settings.kakao_client_id,
                "client_secret": settings.kakao_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            tokens = resp.json()
            resp2 = await client.get(KAKAO_USERINFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            info = resp2.json()
            kakao_id = info.get("id")
            account = info.get("kakao_account", {})
            profile = account.get("profile", {})
            email = account.get("email", "")
            if not email:
                # Kakao 이메일 동의 안 한 경우 고유 ID로 이메일 생성
                email = f"kakao_{kakao_id}@kakao.user"
            return {
                "email": email,
                "name": profile.get("nickname", ""),
                "picture": profile.get("profile_image_url", ""),
            }

    raise AppError("OAUTH_FAILED", "지원하지 않는 provider입니다.")
