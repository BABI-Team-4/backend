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

user_essays_collection = mongo_db["user_essays"]

analyses_collection = mongo_db["analyses"]
advise_results_collection = mongo_db["advise_results"]
recommendations_collection = mongo_db["recommendations"]

usage_collection = mongo_db["usage"]
plans_collection = mongo_db["plans"]

essay_companies_collection = mongo_db["essay_companies"]
