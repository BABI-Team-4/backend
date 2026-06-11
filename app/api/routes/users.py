from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import success_response
from app.db.connections import plans_collection, usage_collection, users_collection
from app.schemas.user import UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return success_response({
        "user_id": str(user["_id"]),
        "email": user["email"],
        "name": user["name"],
        "profile_image_url": user.get("profile_image_url", ""),
        "auth_provider": user["auth_provider"],
        "role": user["role"],
        "plan": user["plan"],
        "created_at": user.get("created_at", ""),
    })


@router.patch("/me")
async def update_me(body: UserUpdate, user: dict = Depends(get_current_user)):
    update = {}
    if body.name is not None:
        update["name"] = body.name
    if update:
        await users_collection.update_one({"_id": user["_id"]}, {"$set": update})
    return success_response({
        "user_id": str(user["_id"]),
        "name": body.name or user["name"],
    })


@router.get("/me/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    usage = await usage_collection.find_one({"user_id": user_id})

    plan_doc = await plans_collection.find_one({"plan": user.get("plan", "free")})
    credits_limit = plan_doc.get("credits_limit", 9) if plan_doc else 9
    library_view_limit = plan_doc.get("library_view_limit", 10) if plan_doc else 10

    now = datetime.now(timezone.utc)
    # Reset date = first day of next month
    if now.month == 12:
        reset_at = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        reset_at = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    return success_response({
        "plan": user.get("plan", "free"),
        "monthly_credits_limit": credits_limit,
        "monthly_credits_used": usage.get("monthly_credits_used", 0) if usage else 0,
        "monthly_library_view_limit": library_view_limit,
        "monthly_library_view_used": usage.get("monthly_library_view_used", 0) if usage else 0,
        "reset_at": reset_at.isoformat(),
    })
