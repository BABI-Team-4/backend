"""
자소서 첨삭 메인 모듈 (OpenAI GPT 버전)

흐름:
  1. 3단계 fallback RAG 검색 (기업 → org_type → 전체)
  2. 프롬프트 구성 (prompt.py)
  3. OpenAI Chat Completions API 호출
  4. JSON 파싱 + 최대 2회 재시도
  5. 결과 dict 반환

사용:
    from app.ai.advisor import advise
    result = advise(draft="...", question="...", company="삼성전자")
"""

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from .search import retrieve
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .jd_data import get_jd_summary

load_dotenv()

# ── ORG_TYPE_MAP (원래 crawling.db에 있던 것) ────────────────────────────────
ORG_TYPE_MAP: dict[str, str] = {
    "삼성전자":   "corp",
    "현대자동차": "corp",
    "SK하이닉스": "corp",
    "LG전자":     "corp",
    "포스코":     "corp",
    "한국전력":   "public",
    "농협은행":   "bank",
    "기업은행":   "bank",
    "신한은행":   "bank",
    "우리은행":   "bank",
    "국민은행":   "bank",
    "하나은행":   "bank",
}

# ── 상수 ─────────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "gpt-4o-mini"
MAX_RETRIES   = 2
MAX_TOKENS    = 3000


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _search_with_fallback(
    query: str,
    company: str,
    n_refs: int,
    min_similarity: float,
) -> tuple[list[dict], bool]:
    # 1단계: 기업 필터
    results = retrieve(query, company=company, n_results=n_refs)
    results = [r for r in results if r["similarity"] >= min_similarity]
    if results:
        return results, False

    # 2단계: org_type 필터
    org_type = ORG_TYPE_MAP.get(company)
    if org_type:
        results = retrieve(query, org_type=org_type, n_results=n_refs)
        results = [r for r in results if r["similarity"] >= min_similarity]
        if results:
            return results, True

    # 3단계: 전체 검색
    results = retrieve(query, n_results=n_refs)
    results = [r for r in results if r["similarity"] >= min_similarity]
    return results, True


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text.strip())


# ── 메인 함수 ─────────────────────────────────────────────────────────────────

def advise(
    draft: str,
    question: str,
    company: str,
    *,
    n_refs: int           = 3,
    min_similarity: float = 0.5,
    model: str            = DEFAULT_MODEL,
) -> dict:
    # 1. RAG 검색
    query = f"{question}\n{draft}"
    refs, ref_warning = _search_with_fallback(
        query=query, company=company, n_refs=n_refs, min_similarity=min_similarity,
    )

    # 2. 참고자소서 평균 글자수
    char_counts = [r.get("char_count", 0) for r in refs if r.get("char_count", 0) > 0]
    avg_ref_chars = int(sum(char_counts) / len(char_counts)) if char_counts else 0

    # 3. 프롬프트 구성
    jd_summary = get_jd_summary(company)
    user_prompt = build_user_prompt(
        draft=draft, question=question, company=company,
        references=refs, avg_ref_chars=avg_ref_chars, jd_summary=jd_summary,
    )

    # 4. OpenAI API 호출
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    parsed: dict = {}
    tokens_used = 0

    for attempt in range(MAX_RETRIES + 1):
        suffix = "\n\n반드시 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요." if attempt > 0 else ""
        response = client.chat.completions.create(
            model=model, max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt + suffix},
            ],
        )
        raw_text = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        try:
            parsed = _extract_json(raw_text)
            break
        except (json.JSONDecodeError, ValueError):
            if attempt < MAX_RETRIES:
                continue
            parsed = {"summary": raw_text[:500], "pros": [], "cons": [], "rewrite": "", "_raw": raw_text}

    # 5. 결과 조합
    rewrite_text = parsed.get("rewrite", "")
    return {
        "draft":         draft,
        "summary":       parsed.get("summary", ""),
        "pros":          parsed.get("pros", []),
        "cons":          parsed.get("cons", []),
        "rewrite":       rewrite_text,
        "input_chars":   len(draft),
        "rewrite_chars": len(rewrite_text),
        "avg_ref_chars": avg_ref_chars,
        "references":  [
            {
                "company":    r["company"],
                "role":       r.get("role", ""),
                "question":   r.get("question", ""),
                "answer":     (r.get("answer") or "")[:300],
                "similarity": r["similarity"],
                "char_count": r.get("char_count", 0),
            }
            for r in refs
        ],
        "ref_warning":   ref_warning,
        "jd_used":       bool(jd_summary),
        "tokens_used":   tokens_used,
        "model":         model,
    }
