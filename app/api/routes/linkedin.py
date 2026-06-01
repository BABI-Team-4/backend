import re
from functools import lru_cache

from ddgs import DDGS
from fastapi import APIRouter, Query

from app.core.responses import success_response

router = APIRouter(tags=["linkedin"])


@router.get("/linkedin-search")
async def search_linkedin_profiles(
    company: str = Query(..., min_length=1),
    position: str = Query(""),
):
    """DuckDuckGo 검색으로 LinkedIn 프로필을 반환합니다."""
    import asyncio

    query = f"site:linkedin.com/in {company} {position}".strip()

    def _search():
        try:
            return DDGS().text(query, max_results=3)
        except Exception:
            return []

    results = await asyncio.to_thread(_search)

    profiles = []
    for r in results:
        link = r.get("href", "")
        if "linkedin.com/in/" not in link:
            continue

        title = r.get("title", "")
        title = re.sub(r"\s*[-–|].*LinkedIn.*$", "", title).strip()

        profiles.append({
            "title": title,
            "link": link,
            "snippet": r.get("body", ""),
        })

    return success_response(profiles)
