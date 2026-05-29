"""Import essays.csv, qna.csv, qna_embeddings.csv into MongoDB."""
import asyncio
import csv
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

CSV_DIR = Path(__file__).resolve().parent.parent.parent.parent  # repo root


def _int_or_none(v: str):
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


async def import_all(csv_dir: str | None = None):
    base = Path(csv_dir) if csv_dir else CSV_DIR
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    # --- essays ---
    essays_path = base / "essays.csv"
    if essays_path.exists():
        rows = []
        with open(essays_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r["_id"] = int(r["id"])
                del r["id"]
                rows.append(r)
        if rows:
            await db["essays"].delete_many({})
            await db["essays"].insert_many(rows)
            print(f"Imported {len(rows)} essays")

    # --- qna ---
    qna_path = base / "qna.csv"
    if qna_path.exists():
        rows = []
        with open(qna_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r["_id"] = int(r["id"])
                del r["id"]
                r["essay_id"] = _int_or_none(r.get("essay_id"))
                r["char_count"] = _int_or_none(r.get("char_count")) or 0
                r["is_valid"] = _int_or_none(r.get("is_valid")) or 0
                rows.append(r)
        if rows:
            await db["qna"].delete_many({})
            await db["qna"].insert_many(rows)
            print(f"Imported {len(rows)} qna")

    # --- qna_embeddings ---
    emb_path = base / "qna_embeddings.csv"
    if emb_path.exists():
        rows = []
        with open(emb_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r["_id"] = int(r["id"])
                del r["id"]
                r["qna_id"] = _int_or_none(r.get("qna_id"))
                rows.append(r)
        if rows:
            await db["qna_embeddings"].delete_many({})
            await db["qna_embeddings"].insert_many(rows)
            print(f"Imported {len(rows)} qna_embeddings")

    client.close()
    print("Done.")


if __name__ == "__main__":
    csv_dir = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(import_all(csv_dir))
