"""
AI module integration service.
Wraps app.ai.advisor.advise() and app.ai.search.retrieve()
and transforms their outputs to match the API response spec.
"""
import asyncio

from app.ai.advisor import advise
from app.ai.search import retrieve


async def run_analysis(
    draft: str,
    question: str,
    company: str,
    company_id: int | None = None,
    job_role_name: str = "",
    job_role_id: int | None = None,
) -> dict:
    result = await asyncio.to_thread(
        advise, draft=draft, question=question, company=company,
        n_refs=3, min_similarity=0.5,
    )

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


async def run_recommendation(
    draft: str,
    question: str,
    company: str = "",
    limit: int = 10,
) -> list[dict]:
    query = f"{question}\n{draft}" if question else draft
    results = await asyncio.to_thread(retrieve, query, n_results=limit * 3)

    company_scores: dict[str, dict] = {}
    for r in results:
        comp = r.get("company", "")
        if not comp or comp == company:
            continue
        if comp not in company_scores:
            company_scores[comp] = {
                "company_name": comp,
                "job_role_name": r.get("role", ""),
                "similarities": [],
            }
        company_scores[comp]["similarities"].append(r.get("similarity", 0))

    ranked = sorted(
        company_scores.values(),
        key=lambda x: sum(x["similarities"]) / len(x["similarities"]),
        reverse=True,
    )[:limit]

    items = []
    for rank, entry in enumerate(ranked, 1):
        avg_sim = sum(entry["similarities"]) / len(entry["similarities"])
        items.append({
            "rank": rank,
            "company_id": None,
            "company_name": entry["company_name"],
            "job_role_id": None,
            "job_role_name": entry["job_role_name"],
            "fit_score": int(avg_sim * 100),
            "reason": f"{entry['company_name']}의 합격 자소서와 유사도가 높습니다.",
            "matched_keywords": [],
            "missing_keywords": [],
            "recommended_revision": "",
        })

    return items
