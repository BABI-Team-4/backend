from fastapi import APIRouter, Query

from app.core.responses import success_response, AppError
from app.db.connections import essays_collection, qna_collection

router = APIRouter(prefix="/library", tags=["library"])


def _parse_year_value(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.get("/tags")
async def list_tags():
    """자소서에서 사용되는 필터 태그 목록 (org_type, hire_type, season, year)"""
    companies = sorted(await essays_collection.distinct("company"))
    org_types = await essays_collection.distinct("org_type")
    hire_types = await essays_collection.distinct("hire_type")
    seasons = await essays_collection.distinct("season")
    raw_years = await essays_collection.distinct("year")
    years = sorted({parsed for y in raw_years if (parsed := _parse_year_value(y)) is not None}, reverse=True)

    return success_response({
        "companies": [c for c in companies if c],
        "org_types": [t for t in org_types if t],
        "hire_types": [t for t in hire_types if t],
        "seasons": [s for s in seasons if s],
        "years": years,
    })


@router.get("")
async def list_essays(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    company: str | None = None,
    role: str | None = None,
    org_type: str | None = None,
    hire_type: str | None = None,
    year: int | None = None,
    season: str | None = None,
    keyword: str | None = None,
):
    """합격 자소서 목록 (페이지네이션 + 필터)"""
    query: dict = {}
    if company:
        query["company"] = {"$regex": company, "$options": "i"}
    if role:
        query["role"] = {"$regex": role, "$options": "i"}
    if org_type:
        query["org_type"] = org_type
    if hire_type:
        query["hire_type"] = hire_type
    if year:
        query["year"] = {"$in": [year, str(year)]}
    if season:
        query["season"] = season
    if keyword:
        keyword_or = [
            {"company": {"$regex": keyword, "$options": "i"}},
            {"role": {"$regex": keyword, "$options": "i"}},
        ]
        parsed_year = _parse_year_value(keyword)
        if parsed_year is not None:
            keyword_or.append({"year": {"$in": [parsed_year, str(parsed_year)]}})
        query["$or"] = keyword_or

    total = await essays_collection.count_documents(query)
    skip = (page - 1) * limit

    cursor = essays_collection.find(query).sort("year", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        essay_id = doc["_id"]  # int
        qna_count = await qna_collection.count_documents({"essay_id": essay_id, "is_valid": 1})
        items.append({
            "essay_id": essay_id,
            "company": doc.get("company", ""),
            "org_type": doc.get("org_type", ""),
            "role": doc.get("role", ""),
            "hire_type": doc.get("hire_type", ""),
            "year": _parse_year_value(doc.get("year")) or 0,
            "season": doc.get("season", ""),
            "university": doc.get("university", ""),
            "major": doc.get("major", ""),
            "source": doc.get("source", ""),
            "qna_count": qna_count,
        })

    return success_response({
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
    })


@router.get("/{essay_id}")
async def get_essay_detail(essay_id: int):
    """합격 자소서 상세 (문항 포함)"""
    doc = await essays_collection.find_one({"_id": essay_id})
    if not doc:
        raise AppError("ESSAY_NOT_FOUND", "해당 자소서를 찾을 수 없습니다.", 404)

    qna_items = []
    async for q in qna_collection.find({"essay_id": essay_id, "is_valid": 1}):
        qna_items.append({
            "qna_id": q["_id"],
            "question": q.get("question", ""),
            "answer": q.get("answer", ""),
            "question_type": q.get("question_type", ""),
            "char_count": q.get("char_count", 0),
        })

    return success_response({
        "essay_id": essay_id,
        "company": doc.get("company", ""),
        "org_type": doc.get("org_type", ""),
        "role": doc.get("role", ""),
        "hire_type": doc.get("hire_type", ""),
        "year": _parse_year_value(doc.get("year")) or 0,
        "season": doc.get("season", ""),
        "university": doc.get("university", ""),
        "major": doc.get("major", ""),
        "source": doc.get("source", ""),
        "qna": qna_items,
    })
