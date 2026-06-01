import math

from fastapi import APIRouter, Query

from app.core.responses import AppError, success_response
from app.db.connections import (
    companies_collection,
    industries_collection,
    job_postings_collection,
    job_roles_collection,
)

router = APIRouter(tags=["companies"])

@router.get("/supported-companies")
async def list_supported_companies(keyword: str = Query("")):
    from app.db.connections import essay_companies_collection
    query: dict = {}
    if keyword.strip():
        query["name"] = {"$regex": keyword.strip(), "$options": "i"}
    docs = await essay_companies_collection.find(query).sort("name", 1).to_list(200)
    return success_response([d["name"] for d in docs])


# --- Industries ---

@router.get("/industries")
async def list_industries():
    docs = await industries_collection.find().to_list(100)
    items = [
        {"industry_id": d.get("industry_id", d["_id"]), "name": d["name"], "description": d.get("description", "")}
        for d in docs
    ]
    return success_response(items)


# --- Job Roles ---

@router.get("/job-roles")
async def list_job_roles(industry_id: int | None = Query(None)):
    query = {}
    if industry_id is not None:
        query["industry_id"] = industry_id
    docs = await job_roles_collection.find(query).to_list(200)
    items = [
        {
            "job_role_id": d.get("job_role_id", d["_id"]),
            "industry_id": d.get("industry_id"),
            "name": d["name"],
            "description": d.get("description", ""),
        }
        for d in docs
    ]
    return success_response(items)


# --- Companies ---

@router.get("/companies")
async def list_companies(
    industry_id: int | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query: dict = {}
    if industry_id is not None:
        query["industry_id"] = industry_id
    if keyword:
        query["name"] = {"$regex": keyword, "$options": "i"}

    total = await companies_collection.count_documents(query)
    skip = (page - 1) * limit
    docs = await companies_collection.find(query).skip(skip).limit(limit).to_list(limit)

    items = [
        {
            "company_id": d.get("company_id", d["_id"]),
            "industry_id": d.get("industry_id"),
            "name": d["name"],
            "company_size": d.get("company_size", ""),
            "logo_url": d.get("logo_url", ""),
        }
        for d in docs
    ]
    return success_response({"items": items, "page": page, "limit": limit, "total": total})


@router.get("/companies/{company_id}")
async def get_company(company_id: int):
    doc = await companies_collection.find_one({"company_id": company_id})
    if not doc:
        doc = await companies_collection.find_one({"_id": company_id})
    if not doc:
        raise AppError("NOT_FOUND", "기업을 찾을 수 없습니다.", 404)
    return success_response({
        "company_id": doc.get("company_id", doc["_id"]),
        "industry_id": doc.get("industry_id"),
        "name": doc["name"],
        "description": doc.get("description", ""),
        "talent_summary": doc.get("talent_summary", ""),
        "talent_keywords": doc.get("talent_keywords", []),
        "preferred_experiences": doc.get("preferred_experiences", []),
    })


@router.get("/companies/{company_id}/job-postings")
async def list_job_postings(company_id: int, job_role_id: int | None = Query(None)):
    query: dict = {"company_id": company_id}
    if job_role_id is not None:
        query["job_role_id"] = job_role_id
    docs = await job_postings_collection.find(query).to_list(100)
    items = [
        {
            "job_posting_id": d.get("job_posting_id", d["_id"]),
            "company_id": d["company_id"],
            "job_role_id": d.get("job_role_id"),
            "title": d.get("title", ""),
            "description": d.get("description", ""),
            "required_keywords": d.get("required_keywords", []),
            "preferred_keywords": d.get("preferred_keywords", []),
        }
        for d in docs
    ]
    return success_response(items)
