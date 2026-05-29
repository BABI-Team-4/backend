import chromadb
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

# MongoDB (async)
mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
mongo_db = mongo_client[settings.mongodb_db_name]

# --- Collections ---
essays_collection = mongo_db["essays"]
qna_collection = mongo_db["qna"]
qna_embeddings_collection = mongo_db["qna_embeddings"]

users_collection = mongo_db["users"]
refresh_tokens_collection = mongo_db["refresh_tokens"]

industries_collection = mongo_db["industries"]
companies_collection = mongo_db["companies"]
job_roles_collection = mongo_db["job_roles"]
job_postings_collection = mongo_db["job_postings"]

chat_sessions_collection = mongo_db["chat_sessions"]
chat_messages_collection = mongo_db["chat_messages"]

analyses_collection = mongo_db["analyses"]
recommendations_collection = mongo_db["recommendations"]

usage_collection = mongo_db["usage"]
plans_collection = mongo_db["plans"]

# ChromaDB (lazy init to avoid connection error at import time)
_chroma_client = None
_chroma_collection = None


def get_chroma_collection():
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        _chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    return _chroma_collection
