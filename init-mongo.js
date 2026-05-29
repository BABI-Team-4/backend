db = db.getSiblingDB("cover_letter");

// Users
db.createCollection("users");
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ auth_provider: 1 });

// Industries
db.createCollection("industries");

// Job Roles
db.createCollection("job_roles");
db.job_roles.createIndex({ industry_id: 1 });

// Companies
db.createCollection("companies");
db.companies.createIndex({ industry_id: 1 });
db.companies.createIndex({ name: "text" });

// Job Postings
db.createCollection("job_postings");
db.job_postings.createIndex({ company_id: 1 });
db.job_postings.createIndex({ job_role_id: 1 });

// Chat Sessions
db.createCollection("chat_sessions");
db.chat_sessions.createIndex({ user_id: 1 });
db.chat_sessions.createIndex({ status: 1 });

// Chat Messages
db.createCollection("chat_messages");
db.chat_messages.createIndex({ session_id: 1, created_at: 1 });

// Essays (기존)
db.createCollection("essays");

// QnA (기존)
db.createCollection("qna");
db.createCollection("qna_embeddings");

// Analyses
db.createCollection("analyses");
db.analyses.createIndex({ session_id: 1 });
db.analyses.createIndex({ status: 1 });

// Recommendations
db.createCollection("recommendations");
db.recommendations.createIndex({ session_id: 1 });

// Usage
db.createCollection("usage");
db.usage.createIndex({ user_id: 1 }, { unique: true });

// Refresh Tokens
db.createCollection("refresh_tokens");
db.refresh_tokens.createIndex({ user_id: 1 });
db.refresh_tokens.createIndex({ token: 1 }, { unique: true });
db.refresh_tokens.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 });

// Plans (seed data)
db.createCollection("plans");
db.plans.insertMany([
  { plan: "free", name: "Free", price: 0, analysis_limit: 2, recommendation_limit: 3 },
  { plan: "basic", name: "Basic", price: 10000, analysis_limit: -1, recommendation_limit: 10 },
  { plan: "pro", name: "Pro", price: 20000, analysis_limit: -1, recommendation_limit: 10 },
]);

// Industries (seed data)
db.industries.insertMany([
  { industry_id: 1, name: "은행", description: "은행 및 금융권" },
  { industry_id: 2, name: "IT", description: "소프트웨어 및 플랫폼" },
  { industry_id: 3, name: "제조", description: "제조업" },
  { industry_id: 4, name: "유통", description: "유통 및 물류" },
  { industry_id: 5, name: "공기업", description: "공공기관 및 공기업" },
]);

// Job Roles (seed data)
db.job_roles.insertMany([
  { job_role_id: 1, industry_id: 1, name: "금융영업", description: "개인/기업 고객 대상 금융 영업" },
  { job_role_id: 2, industry_id: 1, name: "금융IT", description: "금융 시스템 개발 및 운영" },
  { job_role_id: 3, industry_id: 2, name: "백엔드 개발", description: "서버/API 개발" },
  { job_role_id: 4, industry_id: 2, name: "프론트엔드 개발", description: "웹/앱 UI 개발" },
  { job_role_id: 5, industry_id: 2, name: "AI/ML 엔지니어", description: "인공지능 모델 개발" },
  { job_role_id: 6, industry_id: 3, name: "생산관리", description: "제조 공정 관리" },
  { job_role_id: 7, industry_id: 3, name: "연구개발", description: "R&D 직무" },
  { job_role_id: 8, industry_id: 4, name: "유통관리", description: "유통 채널 관리" },
  { job_role_id: 9, industry_id: 5, name: "행정", description: "공공기관 행정 직무" },
]);

// Companies (seed data)
db.companies.insertMany([
  { company_id: 1, industry_id: 1, name: "KB국민은행", company_size: "large_enterprise", talent_summary: "고객 중심 사고와 신뢰성을 갖춘 인재", talent_keywords: ["고객중심", "신뢰", "윤리성", "전문성"], preferred_experiences: ["고객 문제 해결 경험", "금융 서비스 이해"] },
  { company_id: 2, industry_id: 2, name: "삼성전자", company_size: "large_enterprise", talent_summary: "창의적 사고와 도전 정신을 가진 인재", talent_keywords: ["창의", "도전", "협업", "전문성"], preferred_experiences: ["기술 프로젝트 경험", "팀 협업 경험"] },
  { company_id: 3, industry_id: 2, name: "카카오", company_size: "large_enterprise", talent_summary: "사용자 중심 서비스를 만드는 인재", talent_keywords: ["사용자중심", "혁신", "데이터기반", "협업"], preferred_experiences: ["서비스 개발 경험", "대규모 트래픽 경험"] },
  { company_id: 4, industry_id: 2, name: "네이버", company_size: "large_enterprise", talent_summary: "기술로 세상을 변화시키는 인재", talent_keywords: ["기술력", "자기주도", "커뮤니케이션"], preferred_experiences: ["오픈소스 기여", "서비스 운영 경험"] },
  { company_id: 5, industry_id: 3, name: "현대자동차", company_size: "large_enterprise", talent_summary: "모빌리티 혁신을 이끌 인재", talent_keywords: ["혁신", "글로벌", "도전", "협업"], preferred_experiences: ["자동차/모빌리티 관련 경험"] },
  { company_id: 6, industry_id: 3, name: "LG전자", company_size: "large_enterprise", talent_summary: "고객 가치를 창출하는 인재", talent_keywords: ["고객가치", "기술력", "도전정신"], preferred_experiences: ["제품 개발 경험"] },
  { company_id: 7, industry_id: 5, name: "한국전력공사", company_size: "large_enterprise", talent_summary: "공익과 전문성을 갖춘 인재", talent_keywords: ["공익", "전문성", "책임감", "소통"], preferred_experiences: ["에너지/인프라 관련 경험"] },
]);

// Job Postings (seed data)
db.job_postings.insertMany([
  { job_posting_id: 1, company_id: 1, job_role_id: 1, title: "개인금융 영업", description: "개인 고객 대상 금융 상품 상담 및 영업", required_keywords: ["고객관리", "금융지식", "신뢰", "영업역량"], preferred_keywords: ["디지털금융", "데이터분석"] },
  { job_posting_id: 2, company_id: 2, job_role_id: 3, title: "소프트웨어 개발", description: "삼성전자 소프트웨어 개발직", required_keywords: ["프로그래밍", "알고리즘", "시스템설계"], preferred_keywords: ["AI", "임베디드"] },
  { job_posting_id: 3, company_id: 3, job_role_id: 3, title: "서버 개발자", description: "카카오 서버 플랫폼 개발", required_keywords: ["백엔드", "대규모시스템", "데이터베이스"], preferred_keywords: ["MSA", "클라우드"] },
  { job_posting_id: 4, company_id: 4, job_role_id: 4, title: "프론트엔드 개발", description: "네이버 프론트엔드 개발", required_keywords: ["JavaScript", "React", "성능최적화"], preferred_keywords: ["TypeScript", "웹접근성"] },
  { job_posting_id: 5, company_id: 5, job_role_id: 7, title: "자율주행 연구개발", description: "현대자동차 자율주행 R&D", required_keywords: ["자율주행", "센서", "알고리즘"], preferred_keywords: ["딥러닝", "ROS"] },
]);

// Test Users (seed data)
var now = new Date();
db.users.insertMany([
  {
    email: "test@example.com",
    name: "박지훈",
    profile_image_url: "",
    auth_provider: "google",
    role: "user",
    plan: "free",
    created_at: now,
  },
  {
    email: "pro@example.com",
    name: "김서연",
    profile_image_url: "",
    auth_provider: "kakao",
    role: "user",
    plan: "pro",
    created_at: now,
  },
  {
    email: "admin@example.com",
    name: "관리자",
    profile_image_url: "",
    auth_provider: "google",
    role: "admin",
    plan: "pro",
    created_at: now,
  },
]);

// Usage for test users
var testUser = db.users.findOne({ email: "test@example.com" });
var proUser = db.users.findOne({ email: "pro@example.com" });
var adminUser = db.users.findOne({ email: "admin@example.com" });

var resetAt = new Date();
resetAt.setMonth(resetAt.getMonth() + 1);
resetAt.setDate(1);
resetAt.setHours(0, 0, 0, 0);

db.usage.insertMany([
  { user_id: testUser._id.toString(), plan: "free", monthly_analysis_limit: 2, monthly_analysis_used: 0, monthly_recommendation_limit: 3, monthly_recommendation_used: 0, reset_at: resetAt },
  { user_id: proUser._id.toString(), plan: "pro", monthly_analysis_limit: -1, monthly_analysis_used: 3, monthly_recommendation_limit: 10, monthly_recommendation_used: 1, reset_at: resetAt },
  { user_id: adminUser._id.toString(), plan: "pro", monthly_analysis_limit: -1, monthly_analysis_used: 0, monthly_recommendation_limit: 10, monthly_recommendation_used: 0, reset_at: resetAt },
]);

print("✅ cover_letter DB initialized with collections, indexes, seed data, and test users");
