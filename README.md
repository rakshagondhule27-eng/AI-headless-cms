# AI-Powered Headless CMS — V12 Final Submission

**V12.0.0 final submission build.** A final-year B.Tech CSE project combining **Headless CMS architecture, local AI/NLP, machine learning, REST APIs, SQL data management and governed publishing**.

## What the system demonstrates

1. **Content management** — create, edit, categorize, tag and publish content.
2. **Headless delivery** — published content is available independently through REST APIs.
3. **AI assistance** — local generation templates, summarization, keyword extraction, classification and quality scoring.
4. **Machine learning** — TF-IDF features + Logistic Regression for content classification.
5. **Governance** — Draft → Pending Review → Approved → Published with role-based permissions.
6. **Traceability** — content version history and audit logs.
7. **Analytics** — database-backed content, views, status, category and quality insights.
8. **Media** — validated local cover-image upload.
9. **Research support** — ML metrics, confusion matrix, model comparison and documented limitations.

## Technology stack

- Frontend: HTML5, CSS3, JavaScript
- Backend: Python, Flask
- Database: SQLite, SQLAlchemy
- AI/ML: scikit-learn, TF-IDF, Logistic Regression, cosine similarity
- Model persistence: Joblib
- Testing: Pytest

## Recommended environment

Use **Python 3.12** for the smoothest dependency compatibility. Python 3.14 can be problematic for some scientific Python packages depending on the platform and wheel availability.

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python ml/train_model.py
python ml/compare_models.py
python app.py
```

### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ml/train_model.py
python ml/compare_models.py
python app.py
```

Open **http://127.0.0.1:5000**.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@neurocms.local | admin123 |
| Editor | editor@neurocms.local | editor123 |
| Author | author@neurocms.local | author123 |

These are local demonstration credentials only.

## V10 final touches

- System health dashboard indicator
- Governed revision behavior for approved/published content
- Version snapshots preserve category, tags and cover image
- OpenAPI-style JSON catalog at `/api/openapi.json`
- Admin CSV analytics export at `/api/analytics/export`
- Upload file-signature validation
- Security response headers
- Publication-health visualization

## Main pages

- Dashboard
- Content Studio
- AI Content Studio
- ML Research Lab
- Approval Workflow
- Analytics
- Architecture
- Research Notebook
- Audit Trail (Admin)
- API Documentation
- Article view / public API feed

## API examples

### Public content feed

```text
GET /api/public/articles
```

### Published content search

```text
GET /api/search?q=machine%20learning
```

### ML prediction

```text
GET /api/ml/predict?text=deep%20learning%20neural%20networks
```

### Analytics

```text
GET /api/analytics
```

## ML evaluation

The bundled dataset has **50 demonstration samples**. Run the training script to regenerate `ml/metrics.json` and the saved model. Do not claim the resulting score as a real-world benchmark. For a dissertation/publication, replace it with a larger domain-specific dataset and report reproducible train/test results.

## Testing

```bash
pytest -q
```

The repository includes syntax/file smoke tests. On a machine with the listed dependencies installed, also manually verify login, CRUD, AI, ML prediction, workflow, upload, analytics, audit and public API flows before submission.

## Documentation

- `ARCHITECTURE.md`
- `PROJECT_STATUS.md`
- `docs/SUBMISSION_CHECKLIST.md`
- `docs/FINAL_REPORT_CHAPTERS.md`
- `docs/SEMINAR_CONTENT.md`
- `docs/VIVA_QA.md`
- `docs/RESEARCH_REFERENCES.md`
- `docs/DEPLOYMENT.md`
- `docs/DEMO_SCRIPT.md`
- `SECURITY.md`
- `CHANGELOG.md`


## V12 Final UI Polish
The V12 build preserves the V10 backend, database, AI/ML, workflow, audit and API features while adding a more resilient application shell, inline critical styles for reliable first paint, a polished dashboard/content experience, and clearer visual hierarchy.


## V12 advanced capabilities
- Hybrid local vector search and grounded CMS assistant
- Duplicate-content detection
- Editorial intelligence and metadata quality flags
- Versioned external API with hashed API keys and rate limiting
- PostgreSQL-ready configuration and Docker/Gunicorn deployment
- Language, slug, SEO metadata, image alt text and featured-content fields
