"""qna 컬렉션에서 distinct company를 뽑아 essay_companies 컬렉션에 저장."""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


async def main():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGODB_DB_NAME", "cover_letter")]

    companies = await db["qna"].distinct("company")
    companies = sorted(set(c.strip() for c in companies if c and c.strip()))

    coll = db["essay_companies"]
    await coll.drop()
    if companies:
        docs = [{"name": c} for c in companies]
        await coll.insert_many(docs)
        await coll.create_index("name")

    print(f"essay_companies: {len(companies)}개 기업 저장 완료")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
