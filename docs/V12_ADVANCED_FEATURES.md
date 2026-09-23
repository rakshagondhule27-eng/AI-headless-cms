# V12 Advanced Feature Set

## 1. AI Content Intelligence
- Local retrieval over published CMS content using TF-IDF vectors, keyword overlap and title relevance.
- Grounded CMS assistant returns answers assembled from published content and provides source links.
- Duplicate-content detector compares a draft/article against the repository.
- Editorial intelligence reports quality flags, metadata gaps and pending-review actions.

## 2. Headless API Evolution
- Versioned external endpoints under `/api/v1/`.
- API-key authentication through `X-API-Key`.
- In-memory request rate limiting for external API clients.
- API keys are stored as SHA-256 hashes and the raw key is shown only at creation time.

## 3. Content Governance
- Language metadata, slug, SEO description, image alt text and featured flag.
- Existing draft/review/approval/publish workflow remains human-controlled.
- Version history and audit trail remain enabled.

## 4. Production Readiness
- `DATABASE_URL` support for PostgreSQL through psycopg.
- SQLite remains the default for local demonstration.
- Dockerfile with Gunicorn production server.
- Security headers and secure-session configuration retained.

## 5. Research Positioning
The V12 retrieval layer is intentionally local and explainable. It is a vector-space retrieval system based on TF-IDF rather than a transformer embedding model. A future research experiment can compare this baseline against sentence-transformer embeddings on a documented domain dataset.

## Demo sequence
1. Login as Admin.
2. Open Content Studio and create a draft.
3. Use AI Studio to generate/analyze content.
4. Submit → Approve → Publish.
5. Open AI Intelligence → search the published knowledge base.
6. Ask the grounded CMS assistant a question.
7. Run duplicate detection.
8. Open Analytics and ML Lab.
9. Open API Keys and create a client key.
10. Call `/api/v1/articles` with `X-API-Key`.
