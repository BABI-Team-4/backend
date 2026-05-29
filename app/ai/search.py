"""
RAG 검색 유틸리티
- ChromaDB 에서 유사 자소서 Q&A 검색
"""

import logging
import os
import re

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

from app.core.config import settings

COLLECTION  = settings.chroma_collection_name
MODEL_NAME  = settings.embedding_model_name

_NOISE_RE = re.compile(
    r"^\(\d+자[^)\n]*(?:\([^)\n]*\))?\)\s*\n*"
    r"|\b\d+자\s+이내[^\n]*\n*"
    r"|^Guide>\s*\n*"
    r"|^\[[^\]\n]{1,20}\]\s*\n",
    re.MULTILINE,
)

_model = None
_col   = None


def _clean_ref_answer(text: str) -> str:
    text = _NOISE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_model():
    global _model
    if _model is None:
        print(f"[검색] BGE-M3 모델 로딩 중... (첫 실행 시 15~20초 소요)", flush=True)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        print("[검색] 모델 로딩 완료", flush=True)
    return _model


def _get_col():
    global _col
    if _col is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _col = client.get_collection(COLLECTION)
    return _col


def retrieve(
    query: str,
    *,
    company:       str | None = None,
    org_type:      str | None = None,
    question_type: str | None = None,
    n_results:     int        = 5,
) -> list[dict]:
    model = _get_model()
    col   = _get_col()

    vec = model.encode([query], normalize_embeddings=True)[0].tolist()

    where_clauses = []
    if company:
        where_clauses.append({"company": {"$eq": company}})
    if org_type:
        where_clauses.append({"org_type": {"$eq": org_type}})
    if question_type:
        where_clauses.append({"question_type": {"$eq": question_type}})

    where = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    kwargs = dict(
        query_embeddings=[vec],
        n_results=n_results,
        include=["metadatas", "documents", "distances"],
    )
    if where:
        kwargs["where"] = where

    res = col.query(**kwargs)

    results = []
    for meta, doc, dist in zip(
        res["metadatas"][0],
        res["documents"][0],
        res["distances"][0],
    ):
        similarity = round(1 - dist, 4)
        parts    = doc.split("\n", 1)
        question = parts[0] if len(parts) == 2 else ""
        answer   = _clean_ref_answer(parts[1] if len(parts) == 2 else parts[0])

        results.append({
            "company":       meta.get("company", ""),
            "role":          meta.get("role", ""),
            "question_type": meta.get("question_type", ""),
            "source":        meta.get("source", ""),
            "year":          meta.get("year", ""),
            "season":        meta.get("season", ""),
            "question":      question,
            "answer":        answer,
            "char_count":    meta.get("char_count", 0),
            "similarity":    similarity,
            "qna_id":        meta.get("qna_id", 0),
        })

    return results
