import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.responses import AppError, success_response

router = APIRouter(tags=["linkedin"])


@router.get("/linkedin-search")
async def search_linkedin_profiles(
    company: str = Query(..., min_length=1),
    position: str = Query(""),
):
    """Google Custom Search로 LinkedIn 현업자 프로필을 검색합니다."""
    api_key = settings.google_custom_search_api_key
    cx = settings.google_custom_search_cx
    if not api_key or not cx:
        raise AppError("CONFIG_ERROR", "Google Custom Search가 설정되지 않았습니다.", 500)

    query = f"{company} {position}".strip()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cx,
                "q": query,
                "num": 5,
            },
        )

    if resp.status_code != 200:
        raise AppError("SEARCH_ERROR", "LinkedIn 검색에 실패했습니다.", 502)

    data = resp.json()
    items = data.get("items", [])

    profiles = []
    for item in items:
        profiles.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })

    return success_response(profiles)
