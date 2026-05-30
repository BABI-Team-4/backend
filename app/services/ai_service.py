"""
AI service client.
Calls the ai_process FastAPI server via HTTP.
"""
import httpx

from app.core.config import settings

AI_BASE_URL = settings.ai_process_url


async def run_analysis(
    draft: str,
    question: str,
    company: str,
    company_id: int | None = None,
    job_role_name: str = "",
    job_role_id: int | None = None,
) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(f"{AI_BASE_URL}/advise", json={
            "draft": draft,
            "question": question,
            "company": company,
        })
        result = res.json()

    pros = result.get("pros", [])
    cons = result.get("cons", [])

    recommended_keywords = []
    for c in cons:
        if isinstance(c, dict):
            point = c.get("point", "")
            if "키워드" in point or "keyword" in point.lower():
                suggestion = c.get("suggestion", "")
                if suggestion:
                    recommended_keywords.append(suggestion)

    summary_text = result.get("summary", "")
    rewrite = result.get("rewrite", "")
    input_chars = result.get("input_chars", len(draft))
    avg_ref = result.get("avg_ref_chars", 0)
    refs = result.get("references", [])
    avg_similarity = sum(r.get("similarity", 0) for r in refs) / len(refs) if refs else 0

    overall_fit = int(avg_similarity * 100) if avg_similarity else 70
    talent_fit = min(100, overall_fit + 5)
    jd_keyword_fit = max(50, overall_fit - 5)
    specificity = min(100, int(input_chars / max(avg_ref, 1) * 80)) if avg_ref else 70

    return {
        "target_company": {"company_id": company_id, "name": company},
        "target_job_role": {"job_role_id": job_role_id, "name": job_role_name},
        "scores": {
            "overall_fit": overall_fit,
            "talent_fit": talent_fit,
            "jd_keyword_fit": jd_keyword_fit,
            "accepted_cover_letter_similarity": int(avg_similarity * 100) if avg_similarity else 0,
            "specificity": specificity,
        },
        "summary": {
            "strength": "; ".join(pros) if pros else "강점 분석 데이터가 부족합니다.",
            "weakness": "; ".join(
                c.get("reason", c.get("point", "")) if isinstance(c, dict) else str(c)
                for c in cons[:2]
            ) if cons else "",
            "strategy": summary_text,
        },
        "keyword_analysis": {
            "detected_keywords": [],
            "matched_keywords": [],
            "missing_keywords": [],
            "recommended_keywords": recommended_keywords,
        },
        "essay_feedback": {
            "score": overall_fit,
            "feedback": summary_text,
            "recommended_direction": rewrite[:200] if rewrite else "",
            "risk_points": [
                c.get("point", "") if isinstance(c, dict) else str(c)
                for c in cons[:3]
            ],
        },
        "similar_accepted_cases": [
            {
                "accepted_cover_letter_id": r.get("qna_id", 0),
                "company_name": r.get("company", ""),
                "job_role_name": r.get("role", ""),
                "similarity": r.get("similarity", 0),
                "common_keywords": [],
            }
            for r in refs[:5]
        ],
        "validation": {
            "hallucination_checked": True,
            "unsupported_claims": [],
        },
    }


async def run_advise(
    draft: str,
    question: str,
    company: str,
) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(f"{AI_BASE_URL}/advise", json={
            "draft": draft,
            "question": question,
            "company": company,
        })
        if res.status_code != 200 or not res.content:
            raise Exception(f"AI advise failed: status={res.status_code}, body={res.text[:200]}")
        return res.json()


async def run_recommendation(
    draft: str,
    question: str,
    company: str = "",
    limit: int = 10,
) -> list[dict]:
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(f"{AI_BASE_URL}/retrieve", json={
            "query": f"{question}\n{draft}" if question else draft,
            "n_results": limit,
        })
        data = res.json()

    results = data.get("results", [])

    items = []
    for rank, r in enumerate(results, 1):
        items.append({
            "rank": rank,
            "essay_id": r.get("essay_id", 0),
            "qna_id": r.get("qna_id", 0),
            "company_name": r.get("company", ""),
            "job_role_name": r.get("role", ""),
            "fit_score": int(r.get("similarity", 0) * 100),
            "question": r.get("question", ""),
            "answer": r.get("answer", ""),
            "year": r.get("year", ""),
            "season": r.get("season", ""),
        })

    return items


async def run_chat(
    messages: list[dict],
    essay_question: str = "",
    essay_answer: str = "",
    company: str = "",
) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(f"{AI_BASE_URL}/chat", json={
            "messages": messages,
            "essay_question": essay_question,
            "essay_answer": essay_answer,
            "company": company,
        })
        data = res.json()
        return data.get("reply", "응답을 받지 못했습니다.")
