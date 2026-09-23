from flask import Flask, render_template, request, jsonify, redirect, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
from pathlib import Path
from ai_engine import AIEngine
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import inspect as sa_inspect
import os
import json
import csv
import io
import joblib
import hashlib
import re
import secrets
import time
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "12.0.0"
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "local-dev-secret-change-before-deployment"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///" + str(BASE_DIR / "cms.db")).replace("postgres://", "postgresql://", 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
)

db = SQLAlchemy(app)
ai = AIEngine()

UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

# -----------------------------
# Security / response hardening
# -----------------------------
@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store" if request.path.startswith("/api/") else "private, max-age=0, must-revalidate")
    return response

# -----------------------------
# Database models
# -----------------------------
content_tags = db.Table(
    "content_tags",
    db.Column("content_id", db.Integer, db.ForeignKey("content.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="Author")


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)


class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, default="")
    summary = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="Draft")
    views = db.Column(db.Integer, default=0)
    ai_score = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    image_url = db.Column(db.String(500), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    language = db.Column(db.String(20), default="English")
    slug = db.Column(db.String(280), unique=True)
    meta_description = db.Column(db.String(320), default="")
    alt_text = db.Column(db.String(320), default="")
    featured = db.Column(db.Boolean, default=False)

    category = db.relationship("Category", backref="contents")
    author = db.relationship("User", backref="contents")
    tags = db.relationship("Tag", secondary=content_tags, backref="contents")


class ContentVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey("content.id"), nullable=False)
    title = db.Column(db.String(250))
    body = db.Column(db.Text)
    summary = db.Column(db.Text)
    category_id = db.Column(db.Integer)
    image_url = db.Column(db.String(500), default="")
    tags_json = db.Column(db.Text, default="[]")
    version = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.relationship(
        "Content", backref=db.backref("versions", cascade="all, delete-orphan")
    )


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(80), nullable=False)
    entity = db.Column(db.String(80), default="Content")
    entity_id = db.Column(db.Integer)
    details = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")


class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(64), unique=True, nullable=False)
    prefix = db.Column(db.String(12), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)



# -----------------------------
# Helpers / security
# -----------------------------
def current_user():
    uid = session.get("uid")
    return User.query.get(uid) if uid else None


def auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("uid"):
            if request.path.startswith("/api/"):
                return jsonify(error="Authentication required"), 401
            return redirect("/login")
        return f(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                if request.path.startswith("/api/"):
                    return jsonify(error="Authentication required"), 401
                return redirect("/login")
            if user.role not in roles:
                return jsonify(error="Permission denied"), 403
            return f(*args, **kwargs)

        return wrapped

    return decorator


def audit(action, entity="Content", entity_id=None, details=""):
    user = current_user()
    if user:
        db.session.add(
            AuditLog(
                user_id=user.id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                details=str(details)[:500],
            )
        )


def make_slug(title, content_id=None):
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "content"
    slug = base
    n = 2
    while True:
        q = Content.query.filter_by(slug=slug)
        if content_id:
            q = q.filter(Content.id != content_id)
        if not q.first():
            return slug
        slug = f"{base}-{n}"
        n += 1

def generate_api_key():
    raw = "cms_" + secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), raw[:12]

RATE_BUCKET = defaultdict(list)
def rate_limited(bucket, limit=60, window=60):
    now=time.time(); arr=RATE_BUCKET[bucket]
    RATE_BUCKET[bucket]=[x for x in arr if now-x < window]
    if len(RATE_BUCKET[bucket]) >= limit: return True
    RATE_BUCKET[bucket].append(now); return False

def api_key_user():
    supplied=request.headers.get("X-API-Key", "")
    if not supplied: return None
    key=APIKey.query.filter_by(key_hash=hashlib.sha256(supplied.encode()).hexdigest(), active=True).first()
    if key:
        key.last_used_at=datetime.utcnow(); db.session.commit()
    return key

def require_api_key():
    key=api_key_user()
    if not key: return None, (jsonify(error="Valid X-API-Key required"),401)
    if rate_limited(f"api:{key.id}", 120, 60): return None, (jsonify(error="Rate limit exceeded. Try again later."),429)
    return key, None

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def taglist(values):
    result = []
    for value in values or []:
        name = str(value).strip().lower()
        if not name:
            continue
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        result.append(tag)
    return result


def serialize_content(item):
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "summary": item.summary,
        "status": item.status,
        "views": item.views or 0,
        "ai_score": round(item.ai_score or 0, 1),
        "category": item.category.name if item.category else "General",
        "category_id": item.category_id,
        "tags": [tag.name for tag in item.tags],
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "author": item.author.name if item.author else "Unknown",
        "author_id": item.author_id,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "image_url": item.image_url or "/static/visuals/ai.svg",
        "version_count": len(item.versions),
        "language": item.language or "English",
        "slug": item.slug or make_slug(item.title, item.id),
        "meta_description": item.meta_description or (item.summary or "")[:320],
        "alt_text": item.alt_text or item.title,
        "featured": bool(item.featured),
    }


def ml_metrics():
    path = BASE_DIR / "ml" / "metrics.json"
    if not path.exists():
        return {"status": "Model not trained. Run python ml/train_model.py"}
    return json.loads(path.read_text(encoding="utf-8"))


def can_edit_content(item):
    user = current_user()
    return bool(user and (user.role in {"Admin", "Editor"} or item.author_id == user.id))


def workflow_transition(content_id, target):
    item = Content.query.get_or_404(content_id)
    user = current_user()
    if not can_edit_content(item):
        return jsonify(error="Permission denied"), 403

    allowed = {
        "submit": ({"Draft", "Rejected"}, "Pending Review"),
        "approve": ({"Pending Review"}, "Approved"),
        "reject": ({"Pending Review"}, "Rejected"),
        "publish": ({"Approved", "Draft"}, "Published"),
    }
    if target not in allowed:
        return jsonify(error="Invalid workflow action"), 400

    source_states, new_status = allowed[target]
    if item.status not in source_states:
        return jsonify(error=f"Cannot {target} content in {item.status} state"), 400
    if target in {"approve", "reject", "publish"} and user.role not in {"Admin", "Editor"}:
        return jsonify(error="Only Admin or Editor can perform this action"), 403

    item.status = new_status
    if target == "submit":
        item.submitted_at = datetime.utcnow()
    if target == "publish":
        item.published_at = datetime.utcnow()

    audit(target.upper(), entity_id=item.id, details=item.title)
    db.session.commit()
    return jsonify(serialize_content(item))


# -----------------------------
# Error handling
# -----------------------------
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(error="Resource not found"), 404
    return render_template("error.html", code=404, message="The requested page was not found."), 404


@app.errorhandler(413)
def too_large(error):
    if request.path.startswith("/api/"):
        return jsonify(error="File is too large. Maximum size is 5 MB."), 413
    return render_template("error.html", code=413, message="The uploaded file is too large."), 413


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    if request.path.startswith("/api/"):
        return jsonify(error="Internal server error"), 500
    return render_template("error.html", code=500, message="Something went wrong. Check the terminal for details."), 500


# -----------------------------
# Authentication / pages
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("uid"):
        return redirect("/")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session.clear()
            session["uid"] = user.id
            return redirect("/")
        return render_template("login.html", error="Invalid email or password")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.get("/")
@auth
def home():
    return render_template("dashboard.html", user=current_user())


@app.get("/content")
@auth
def content_page():
    return render_template("content.html", categories=Category.query.order_by(Category.name).all(), user=current_user())


@app.get("/ai")
@auth
def ai_page():
    return render_template("ai.html", user=current_user())


@app.get("/ml-lab")
@auth
def ml_lab():
    return render_template("ml_lab.html", user=current_user())


@app.get("/workflow")
@auth
def workflow_page():
    return render_template("workflow.html", user=current_user())


@app.get("/analytics")
@auth
def analytics_page():
    return render_template("analytics.html", user=current_user())


@app.get("/architecture")
@auth
def architecture_page():
    return render_template("architecture.html", user=current_user())


@app.get("/research")
@auth
def research_page():
    return render_template("research.html", user=current_user())


@app.get("/api-keys")
@role_required("Admin")
def api_keys_page():
    return render_template("api_keys.html", user=current_user())


@app.get("/audit")
@role_required("Admin")
def audit_page():
    return render_template("audit.html", user=current_user())


@app.get("/article/<int:content_id>")
def article(content_id):
    item = Content.query.get_or_404(content_id)
    if item.status != "Published" and not session.get("uid"):
        return "Not found", 404
    item.views = (item.views or 0) + 1
    db.session.commit()
    return render_template("article.html", item=item)


# -----------------------------
# Core APIs
# -----------------------------
@app.get("/api/me")
@auth
def me():
    user = current_user()
    return jsonify(id=user.id, name=user.name, email=user.email, role=user.role)


@app.get("/api/dashboard")
@auth
def dashboard_api():
    total = Content.query.count()
    published = Content.query.filter_by(status="Published").count()
    drafts = Content.query.filter_by(status="Draft").count()
    review = Content.query.filter_by(status="Pending Review").count()
    ai_count = Content.query.filter(Content.ai_score > 0).count()
    views = db.session.query(db.func.sum(Content.views)).scalar() or 0
    recent = Content.query.order_by(Content.updated_at.desc()).limit(6).all()
    return jsonify(
        total=total,
        published=published,
        drafts=drafts,
        review=review,
        ai_generated=ai_count,
        views=views,
        recent=[serialize_content(x) for x in recent],
        role=current_user().role,
    )


@app.get("/api/content")
@auth
def contents():
    return jsonify([serialize_content(x) for x in Content.query.order_by(Content.updated_at.desc()).all()])


@app.post("/api/content")
@auth
def create_content():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    if not title:
        return jsonify(error="Title is required"), 400
    if not body:
        return jsonify(error="Body is required"), 400

    # New content always starts as Draft. Publishing is intentionally handled
    # through the governed workflow so every publication has an audit event.
    status = "Draft"

    category_id = data.get("category_id")
    category = Category.query.get(int(category_id)) if category_id else None
    item = Content(
        title=title,
        body=body,
        summary=str(data.get("summary", "")).strip() or ai.summarize(body),
        status=status,
        category=category,
        author_id=current_user().id,
        image_url=str(data.get("image_url", "")).strip() or "/static/visuals/ai.svg",
        ai_score=ai.score(title, body),
        language=str(data.get("language", "English")),
        slug=make_slug(title),
        meta_description=str(data.get("meta_description", "")).strip()[:320],
        alt_text=str(data.get("alt_text", title)).strip()[:320],
        featured=bool(data.get("featured", False)),
    )
    item.tags = taglist(data.get("tags", []))
    db.session.add(item)
    db.session.flush()
    db.session.add(ContentVersion(content_id=item.id, title=item.title, body=item.body, summary=item.summary, category_id=item.category_id, image_url=item.image_url, tags_json=json.dumps([tag.name for tag in item.tags]), version=1))
    audit("CREATE", entity_id=item.id, details=item.title)
    db.session.commit()
    return jsonify(serialize_content(item)), 201


@app.put("/api/content/<int:content_id>")
@auth
def update_content(content_id):
    item = Content.query.get_or_404(content_id)
    data = request.get_json(silent=True) or {}
    if not can_edit_content(item):
        return jsonify(error="Permission denied"), 403

    title = str(data.get("title", item.title)).strip()
    body = str(data.get("body", item.body)).strip()
    if not title or not body:
        return jsonify(error="Title and body are required"), 400

    requested_status = str(data.get("status", item.status))
    if requested_status not in {"Draft", "Pending Review", "Approved", "Published", "Rejected"}:
        requested_status = item.status
    if requested_status in {"Approved", "Published", "Pending Review"} and current_user().role not in {"Admin", "Editor"}:
        return jsonify(error="Use the governed workflow for review and publication"), 403

    # Editing already-reviewed/published content creates a new draft revision.
    # This prevents silent changes to content that has already been approved.
    if item.status in {"Published", "Approved", "Pending Review"}:
        item.status = "Draft"
    else:
        item.status = requested_status

    item.title = title
    item.body = body
    item.summary = str(data.get("summary", "")).strip() or ai.summarize(body)
    item.image_url = str(data.get("image_url", item.image_url or "/static/visuals/ai.svg")).strip()
    if data.get("category_id"):
        item.category = Category.query.get(int(data["category_id"]))
    item.language = str(data.get("language", item.language or "English"))[:20]
    item.slug = make_slug(title, item.id)
    item.meta_description = str(data.get("meta_description", item.meta_description or "")).strip()[:320]
    item.alt_text = str(data.get("alt_text", item.alt_text or title)).strip()[:320]
    item.featured = bool(data.get("featured", item.featured))
    item.tags = taglist(data.get("tags", []))
    item.ai_score = ai.score(item.title, item.body)
    if item.status == "Published" and not item.published_at:
        item.published_at = datetime.utcnow()

    last = ContentVersion.query.filter_by(content_id=item.id).order_by(ContentVersion.version.desc()).first()
    next_version = (last.version + 1) if last else 1
    db.session.add(ContentVersion(content_id=item.id, title=item.title, body=item.body, summary=item.summary, category_id=item.category_id, image_url=item.image_url, tags_json=json.dumps([tag.name for tag in item.tags]), version=next_version))
    audit("UPDATE", entity_id=item.id, details=item.title)
    db.session.commit()
    return jsonify(serialize_content(item))


@app.delete("/api/content/<int:content_id>")
@role_required("Admin")
def delete_content(content_id):
    item = Content.query.get_or_404(content_id)
    title = item.title
    audit("DELETE", entity_id=item.id, details=title)
    db.session.delete(item)
    db.session.commit()
    return jsonify(ok=True)


@app.post("/api/content/<int:content_id>/submit")
@auth
def submit_content(content_id):
    return workflow_transition(content_id, "submit")


@app.post("/api/content/<int:content_id>/approve")
@role_required("Admin", "Editor")
def approve_content(content_id):
    return workflow_transition(content_id, "approve")


@app.post("/api/content/<int:content_id>/reject")
@role_required("Admin", "Editor")
def reject_content(content_id):
    return workflow_transition(content_id, "reject")


@app.post("/api/content/<int:content_id>/publish")
@role_required("Admin", "Editor")
def publish_content(content_id):
    return workflow_transition(content_id, "publish")


@app.get("/api/workflow/pending")
@auth
def workflow_pending():
    items = Content.query.filter_by(status="Pending Review").order_by(Content.submitted_at.asc()).all()
    return jsonify([serialize_content(x) for x in items])


# -----------------------------
# AI / ML APIs
# -----------------------------
@app.post("/api/ai")
@auth
def ai_api():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    mode = data.get("mode", "content")
    if not text:
        return jsonify(error="Enter a topic or text"), 400
    return jsonify(ai.generate(text, mode))


@app.post("/api/analyze")
@auth
def analyze():
    text = str((request.get_json(silent=True) or {}).get("text", "")).strip()
    if not text:
        return jsonify(error="Paste some text first"), 400
    return jsonify(
        summary=ai.summarize(text),
        keywords=ai.keywords(text),
        category=ai.classify(text),
        confidence=ai.confidence(text),
        top_predictions=ai.probabilities(text)[:3],
        quality=ai.score("Analysis", text),
        readability=ai.readability(text),
    )


@app.get("/api/ai/health")
def ai_health():
    return jsonify(
        status="ready",
        engine="Local NLP + TF-IDF + Logistic Regression",
        features=["generation templates", "classification", "confidence", "summarization", "keywords", "quality scoring", "similarity search", "recommendations"],
    )


@app.get("/api/ml/metrics")
@auth
def api_ml_metrics():
    return jsonify(ml_metrics())


@app.get("/api/ml/comparison")
@auth
def api_ml_comparison():
    path = BASE_DIR / "ml" / "comparison.json"
    if not path.exists():
        return jsonify({})
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/ml/predict")
@auth
def api_ml_predict():
    text = request.args.get("text", "").strip()
    if not text:
        return jsonify(error="Provide text"), 400
    model_path = BASE_DIR / "ml" / "cms_classifier.joblib"
    if not model_path.exists():
        return jsonify(error="Model not trained. Run python ml/train_model.py"), 503
    model = joblib.load(model_path)
    prediction = model.predict([text])[0]
    probabilities = model.predict_proba([text])[0] if hasattr(model, "predict_proba") else []
    ordered = sorted(zip(model.classes_, probabilities), key=lambda pair: pair[1], reverse=True)
    return jsonify(
        category=prediction,
        confidence=round(float(ordered[0][1]) * 100, 1) if ordered else None,
        top_predictions=[{"category": c, "confidence": round(float(p) * 100, 1)} for c, p in ordered[:3]],
    )


# -----------------------------
# Advanced AI / platform capabilities
# -----------------------------
@app.get("/intelligence")
@auth
def intelligence_page():
    return render_template("intelligence.html", user=current_user())

@app.get("/api/intelligence/insights")
@auth
def intelligence_insights():
    items=Content.query.all()
    published=[x for x in items if x.status=="Published"]
    low=[x for x in items if (x.ai_score or 0)<60]
    missing=[x for x in items if not x.tags or not x.summary]
    return jsonify(
        total=len(items), published=len(published), drafts=sum(x.status=="Draft" for x in items),
        low_quality=len(low), metadata_gaps=len(missing), featured=sum(bool(x.featured) for x in items),
        languages=sorted({x.language or "English" for x in items}),
        top_categories=[{"name":n,"count":c} for n,c in db.session.query(Category.name,db.func.count(Content.id)).join(Content,Content.category_id==Category.id,isouter=True).group_by(Category.id).order_by(db.func.count(Content.id).desc()).limit(8).all()],
        actions=[
            {"type":"quality","count":len(low),"message":"Items below the editorial quality threshold"},
            {"type":"metadata","count":len(missing),"message":"Items missing summary or tags"},
            {"type":"review","count":Content.query.filter_by(status="Pending Review").count(),"message":"Items waiting for human review"},
        ])

@app.post("/api/intelligence/chat")
@auth
def intelligence_chat():
    data=request.get_json(silent=True) or {}; q=str(data.get("message","")).strip()
    if not q: return jsonify(error="Enter a question"),400
    published=Content.query.filter_by(status="Published").all()
    if not published: return jsonify(answer="There is no published content to search yet.",sources=[])
    # Retrieval layer: TF-IDF vector search + token overlap, deliberately local and explainable.
    texts=[x.title+" "+x.summary+" "+x.body for x in published]
    matrix=TfidfVectorizer(stop_words="english",ngram_range=(1,2)).fit_transform(texts+[q]) if len(texts)>0 else None
    sims=cosine_similarity(matrix[-1],matrix[:-1])[0] if matrix is not None else []
    qwords=set(ai.keywords(q,12)); ranked=[]
    for score,item in zip(sims,published):
        overlap=len(qwords & set(ai.keywords(item.title+" "+item.body,20)))
        ranked.append((float(score)+0.03*overlap,item))
    ranked.sort(key=lambda z:z[0],reverse=True)
    selected=[x for score,x in ranked[:3] if score>0]
    if not selected:
        return jsonify(answer="I could not find a strong match in the published CMS knowledge base.",sources=[])
    snippets=[]
    for x in selected:
        snippets.append(f"{x.title}: {x.summary or ai.summarize(x.body)}")
    answer="Based on the published CMS knowledge base:\n\n"+"\n\n".join(snippets)
    return jsonify(answer=answer,sources=[{"id":x.id,"title":x.title,"category":x.category.name if x.category else "General","url":f"/article/{x.id}"} for x in selected])

@app.get("/api/intelligence/duplicates/<int:content_id>")
@auth
def duplicate_check(content_id):
    target=Content.query.get_or_404(content_id)
    candidates=Content.query.filter(Content.id!=content_id).all()
    if not candidates:return jsonify(matches=[])
    texts=[target.title+" "+target.body]+[x.title+" "+x.body for x in candidates]
    vec=TfidfVectorizer(stop_words="english",ngram_range=(1,2)).fit_transform(texts)
    sims=cosine_similarity(vec[0:1],vec[1:])[0]
    ranked=sorted(zip(sims,candidates),key=lambda z:z[0],reverse=True)[:8]
    return jsonify(matches=[{"id":x.id,"title":x.title,"status":x.status,"similarity":round(float(score)*100,1)} for score,x in ranked if score>0.15])

@app.get("/api/intelligence/search")
def intelligence_search():
    q=request.args.get("q","").strip();
    if not q:return jsonify(error="Query required"),400
    items=Content.query.filter_by(status="Published").all()
    if rate_limited(f"search:{request.remote_addr}",120,60): return jsonify(error="Rate limit exceeded"),429
    if not items:return jsonify(results=[])
    texts=[x.title+" "+x.summary+" "+x.body for x in items]
    vec=TfidfVectorizer(stop_words="english",ngram_range=(1,2)).fit_transform(texts+[q]); sims=cosine_similarity(vec[-1],vec[:-1])[0]
    qwords=set(ai.keywords(q,12)); ranked=[]
    for score,x in zip(sims,items):
        overlap=len(qwords & set(ai.keywords(x.title+" "+x.body,20)))
        title_boost=.12 if any(w in x.title.lower() for w in qwords) else 0
        ranked.append((float(score)+.025*overlap+title_boost,x))
    ranked.sort(key=lambda z:z[0],reverse=True)
    return jsonify(results=[dict(serialize_content(x),relevance=round(min(1,score)*100,1)) for score,x in ranked[:10] if score>0])

@app.post("/api/admin/api-keys")
@role_required("Admin")
def create_api_key():
    data=request.get_json(silent=True) or {}; name=str(data.get("name","External Client")).strip()[:100] or "External Client"
    raw,h,prefix=generate_api_key(); db.session.add(APIKey(name=name,key_hash=h,prefix=prefix)); audit("API_KEY_CREATE",entity="APIKey",details=name); db.session.commit()
    return jsonify(name=name,api_key=raw,prefix=prefix,note="Store this key securely; it will not be shown again."),201

@app.delete("/api/admin/api-keys/<int:key_id>")
@role_required("Admin")
def revoke_api_key(key_id):
    key=APIKey.query.get_or_404(key_id)
    key.active=False
    audit("API_KEY_REVOKE",entity="APIKey",entity_id=key.id,details=key.name)
    db.session.commit()
    return jsonify(ok=True)

@app.get("/api/admin/api-keys")
@role_required("Admin")
def list_api_keys():
    return jsonify([{"id":x.id,"name":x.name,"prefix":x.prefix,"active":x.active,"created_at":x.created_at.isoformat(),"last_used_at":x.last_used_at.isoformat() if x.last_used_at else None} for x in APIKey.query.order_by(APIKey.created_at.desc()).all()])

@app.get("/api/v1/articles")
def api_v1_articles():
    key,err=require_api_key()
    if err:return err
    try: limit=min(max(int(request.args.get("limit",20)),1),100)
    except ValueError: limit=20
    return jsonify(version="1",data=[serialize_content(x) for x in Content.query.filter_by(status="Published").order_by(Content.published_at.desc()).limit(limit).all()])

@app.get("/api/v1/search")
def api_v1_search():
    key,err=require_api_key()
    if err:return err
    q=request.args.get("q","").strip()
    if not q:return jsonify(error="q is required"),400
    # reuse local search implementation without requiring a browser session
    items=Content.query.filter_by(status="Published").all(); texts=[x.title+" "+x.summary+" "+x.body for x in items]
    if not items:return jsonify(version="1",data=[])
    vec=TfidfVectorizer(stop_words="english",ngram_range=(1,2)).fit_transform(texts+[q]); sims=cosine_similarity(vec[-1],vec[:-1])[0]
    ranked=sorted(zip(sims,items),key=lambda z:z[0],reverse=True)
    return jsonify(version="1",data=[dict(serialize_content(x),relevance=round(float(score)*100,1)) for score,x in ranked[:10]])

# -----------------------------
# Search / versions / media
# -----------------------------
@app.get("/api/search")
def search_api():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    try:
        limit = min(max(int(request.args.get("limit", 10)), 1), 50)
    except ValueError:
        limit = 10

    query = Content.query.filter_by(status="Published")
    if category:
        query = query.join(Category).filter(Category.name.ilike(f"%{category}%"))
    items = query.all()
    if not q:
        return jsonify([dict(serialize_content(x), relevance=0) for x in items[:limit]])

    texts = [x.title + " " + x.body + " " + x.summary for x in items] + [q]
    vectorizer = ai.vectorizer
    matrix = vectorizer.transform(texts)
    similarities = cosine_similarity(matrix[-1], matrix[:-1])[0] if items else []
    ranked = sorted(zip(similarities, items), key=lambda pair: pair[0], reverse=True)
    return jsonify([dict(serialize_content(item), relevance=round(float(score) * 100, 1)) for score, item in ranked[:limit] if score > 0])


@app.get("/api/content/<int:content_id>/versions")
@auth
def versions(content_id):
    Content.query.get_or_404(content_id)
    rows = ContentVersion.query.filter_by(content_id=content_id).order_by(ContentVersion.version.desc()).all()
    return jsonify([
        {"version": v.version, "title": v.title, "summary": v.summary, "category_id": v.category_id, "image_url": v.image_url, "tags": json.loads(v.tags_json or "[]"), "created_at": v.created_at.isoformat()}
        for v in rows
    ])


@app.post("/api/content/<int:content_id>/restore/<int:version>")
@auth
def restore_version(content_id, version):
    item = Content.query.get_or_404(content_id)
    if not can_edit_content(item):
        return jsonify(error="Permission denied"), 403
    version_row = ContentVersion.query.filter_by(content_id=content_id, version=version).first_or_404()
    item.title = version_row.title or item.title
    item.body = version_row.body or ""
    item.summary = version_row.summary or ai.summarize(item.body)
    if version_row.category_id:
        item.category = db.session.get(Category, version_row.category_id) or item.category
    if version_row.image_url:
        item.image_url = version_row.image_url
    try:
        item.tags = taglist(json.loads(version_row.tags_json or "[]"))
    except (TypeError, json.JSONDecodeError):
        pass
    item.status = "Draft"
    item.ai_score = ai.score(item.title, item.body)
    last = ContentVersion.query.filter_by(content_id=content_id).order_by(ContentVersion.version.desc()).first()
    next_version = (last.version + 1) if last else 1
    db.session.add(ContentVersion(content_id=content_id, title=item.title, body=item.body, summary=item.summary, category_id=item.category_id, image_url=item.image_url, tags_json=json.dumps([tag.name for tag in item.tags]), version=next_version))
    audit("RESTORE", entity_id=content_id, details=f"Restored version {version}")
    db.session.commit()
    return jsonify(serialize_content(item))


@app.post("/api/upload")
@auth
def upload_media():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Select an image file"), 400
    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return jsonify(error="Allowed image types: PNG, JPG, JPEG, WEBP, GIF"), 400
    header = file.stream.read(16)
    file.stream.seek(0)
    signatures = (header.startswith(b"\x89PNG"), header.startswith(b"\xff\xd8\xff"), header.startswith(b"GIF8"), header.startswith(b"RIFF") and header[8:12] == b"WEBP")
    if not any(signatures):
        return jsonify(error="The uploaded file does not appear to be a supported image"), 400
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    final_name = f"{stamp}_{filename}"
    file.save(UPLOAD_DIR / final_name)
    audit("UPLOAD", entity="Media", details=final_name)
    db.session.commit()
    return jsonify(url=f"/static/uploads/{final_name}", filename=final_name), 201


@app.get("/media/<path:filename>")
def media(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# -----------------------------
# Analytics / governance / docs
# -----------------------------
@app.get("/api/analytics")
@auth
def analytics_api():
    total = Content.query.count()
    published = Content.query.filter_by(status="Published").count()
    views = db.session.query(db.func.sum(Content.views)).scalar() or 0
    ai_count = Content.query.filter(Content.ai_score > 0).count()
    avg_quality = db.session.query(db.func.avg(Content.ai_score)).scalar() or 0

    top_content = Content.query.order_by(Content.views.desc(), Content.updated_at.desc()).limit(10).all()
    category_rows = (
        db.session.query(Category.name, db.func.count(Content.id))
        .join(Content, Content.category_id == Category.id, isouter=True)
        .group_by(Category.id)
        .order_by(db.func.count(Content.id).desc())
        .all()
    )
    status_rows = db.session.query(Content.status, db.func.count(Content.id)).group_by(Content.status).all()

    quality_buckets = {"High (80–100)": 0, "Medium (60–79)": 0, "Needs improvement (<60)": 0}
    for item in Content.query.all():
        score = item.ai_score or 0
        if score >= 80:
            quality_buckets["High (80–100)"] += 1
        elif score >= 60:
            quality_buckets["Medium (60–79)"] += 1
        else:
            quality_buckets["Needs improvement (<60)"] += 1

    return jsonify(
        total=total,
        published=published,
        views=views,
        ai_assisted=ai_count,
        average_quality=round(float(avg_quality), 1),
        publication_rate=round((published / total) * 100, 1) if total else 0,
        top_content=[{"id": x.id, "title": x.title, "views": x.views or 0, "category": x.category.name if x.category else "General"} for x in top_content],
        categories=[{"name": name, "count": count} for name, count in category_rows],
        statuses=[{"status": name, "count": count} for name, count in status_rows],
        quality=[{"name": name, "count": count} for name, count in quality_buckets.items()],
    )


@app.get("/api/recommendations/<int:content_id>")
@auth
def recommendations(content_id):
    target = Content.query.get_or_404(content_id)
    candidates = Content.query.filter(Content.id != content_id, Content.status == "Published").all()
    results = ai.recommend(target, candidates, limit=5)
    return jsonify([dict(serialize_content(item), relevance=score) for item, score in results])


@app.get("/api/audit")
@role_required("Admin")
def audit_api():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify([
        {"action": x.action, "entity": x.entity, "entity_id": x.entity_id, "user": x.user.name if x.user else "Unknown", "details": x.details, "created_at": x.created_at.isoformat()}
        for x in logs
    ])


@app.get("/api/public/articles")
def public_articles():
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except ValueError:
        limit = 20
    return jsonify([serialize_content(x) for x in Content.query.filter_by(status="Published").order_by(Content.published_at.desc()).limit(limit).all()])


@app.get("/api/health")
def system_health():
    model_path = BASE_DIR / "ml" / "cms_classifier.joblib"
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "healthy"
    except Exception:
        database = "unavailable"
    return jsonify(
        status="healthy" if database == "healthy" and model_path.exists() else "degraded",
        version=APP_VERSION,
        database=database,
        ml_model="ready" if model_path.exists() else "missing",
        environment=os.getenv("APP_ENV", "development"),
        api_version="v1",
        api_key_support=True,
    )


@app.get("/api/categories")
@auth
def categories_api():
    return jsonify([{"id": c.id, "name": c.name, "description": c.description} for c in Category.query.order_by(Category.name).all()])


@app.get("/api/analytics/export")
@role_required("Admin")
def analytics_export():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "title", "category", "status", "views", "quality", "author", "updated_at"])
    for item in Content.query.order_by(Content.updated_at.desc()).all():
        writer.writerow([item.id, item.title, item.category.name if item.category else "General", item.status, item.views or 0, round(item.ai_score or 0, 1), item.author.name if item.author else "Unknown", item.updated_at.isoformat() if item.updated_at else ""])
    response = app.response_class(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=ai_cms_analytics.csv"
    return response


@app.get("/api/openapi.json")
@auth
def openapi_json():
    paths = {}
    for method, path, description in [
        ("get", "/api/public/articles", "Public published content feed"),
        ("get", "/api/content", "List authenticated content"),
        ("post", "/api/content", "Create draft content"),
        ("put", "/api/content/{id}", "Update content"),
        ("delete", "/api/content/{id}", "Delete content (Admin)"),
        ("post", "/api/content/{id}/submit", "Submit content for review"),
        ("post", "/api/content/{id}/approve", "Approve content"),
        ("post", "/api/content/{id}/reject", "Reject content"),
        ("post", "/api/content/{id}/publish", "Publish approved content"),
        ("post", "/api/ai", "Generate AI-assisted content"),
        ("post", "/api/analyze", "Analyze text"),
        ("get", "/api/ml/predict", "Predict content category"),
        ("get", "/api/ml/metrics", "Read ML evaluation metrics"),
        ("get", "/api/search", "Semantic search over published content"),
        ("get", "/api/analytics", "Read analytics"),
        ("get", "/api/health", "System health check"),
        ("get", "/api/intelligence/search", "Hybrid local vector search"),
        ("post", "/api/intelligence/chat", "Grounded CMS knowledge assistant"),
        ("get", "/api/intelligence/duplicates/{id}", "Duplicate-content detection"),
        ("get", "/api/intelligence/insights", "Editorial intelligence"),
        ("get", "/api/v1/articles", "Versioned API feed; requires X-API-Key"),
        ("get", "/api/v1/search", "Versioned API search; requires X-API-Key"),
    ]:
        paths.setdefault(path, {})[method] = {"summary": description, "responses": {"200": {"description": "Successful response"}}}
    return jsonify(openapi="3.0.3", info={"title": "AI-Powered Headless CMS API", "version": APP_VERSION}, servers=[{"url": request.url_root.rstrip("/")}], paths=paths)


@app.get("/api/docs")
@auth
def docs():
    endpoints = [
        ("GET", "/api/health", "System health and component readiness."),
        ("GET", "/api/openapi.json", "Machine-readable OpenAPI-style endpoint catalog."),
        ("GET", "/api/public/articles", "Public published-content feed for websites and other clients."),
        ("GET", "/api/content", "List managed content for authenticated users."),
        ("POST", "/api/content", "Create content with category, tags and cover image."),
        ("PUT", "/api/content/<id>", "Update content and create a new version snapshot."),
        ("DELETE", "/api/content/<id>", "Admin-only content deletion."),
        ("POST", "/api/upload", "Upload a validated image to the media library."),
        ("GET", "/api/content/<id>/versions", "Read version history."),
        ("POST", "/api/content/<id>/restore/<version>", "Restore a previous version as a new version."),
        ("POST", "/api/ai", "Generate local AI-assisted title, summary, body and keywords."),
        ("POST", "/api/analyze", "Analyze summary, keywords, category, quality and readability."),
        ("GET", "/api/search?q=...", "Search published content using TF-IDF similarity."),
        ("GET", "/api/ml/metrics", "Read model evaluation metrics."),
        ("GET", "/api/ml/predict?text=...", "Predict content category with the trained model."),
        ("GET", "/api/analytics", "Read content and engagement analytics."),
        ("GET", "/api/recommendations/<id>", "Return similar published content."),
        ("GET", "/api/intelligence/search?q=...", "Hybrid local vector search with title and keyword relevance."),
        ("POST", "/api/intelligence/chat", "Retrieve grounded answers from published CMS content."),
        ("GET", "/api/intelligence/duplicates/<id>", "Detect semantically similar existing content."),
        ("GET", "/api/intelligence/insights", "Content quality, metadata and editorial intelligence."),
        ("POST", "/api/admin/api-keys", "Admin-only creation of external API keys."),
        ("DELETE", "/api/admin/api-keys/{id}", "Admin-only API key revocation."),
        ("GET", "/api/v1/articles", "Versioned external API feed using X-API-Key."),
        ("GET", "/api/v1/search?q=...", "Versioned external search using X-API-Key."),
        ("GET", "/api/categories", "List available content categories."),
        ("GET", "/api/analytics/export", "Admin-only CSV analytics export."),
        ("GET", "/api/audit", "Admin-only audit trail."),
        ("GET", "/api/ai/health", "Check local AI engine status."),
    ]
    return render_template("api_docs.html", endpoints=endpoints, user=current_user())


# -----------------------------
# Database migration / seed
# -----------------------------
def migrate_schema():
    inspector = sa_inspect(db.engine)
    content_columns = {c["name"] for c in inspector.get_columns("content")}
    additions = [("author_id", "INTEGER"), ("submitted_at", "DATETIME"), ("published_at", "DATETIME"), ("image_url", "VARCHAR(500)"), ("language", "VARCHAR(20)"), ("slug", "VARCHAR(280)"), ("meta_description", "VARCHAR(320)"), ("alt_text", "VARCHAR(320)"), ("featured", "BOOLEAN")]
    if db.engine.dialect.name == "sqlite":
        for name, ddl in additions:
            if name not in content_columns:
                db.session.execute(db.text(f"ALTER TABLE content ADD COLUMN {name} {ddl}"))
    else:
        for name, ddl in additions:
            if name not in content_columns:
                db.session.execute(db.text(f"ALTER TABLE content ADD COLUMN {name} {ddl}"))
    version_columns = {c["name"] for c in inspector.get_columns("content_version")}
    for name, ddl in [("category_id", "INTEGER"), ("image_url", "VARCHAR(500)"), ("tags_json", "TEXT")]:
        if name not in version_columns:
            db.session.execute(db.text(f"ALTER TABLE content_version ADD COLUMN {name} {ddl}"))
    db.session.commit()
    for item in Content.query.all():
        if not item.slug: item.slug=make_slug(item.title,item.id)
        if not item.meta_description: item.meta_description=(item.summary or ai.summarize(item.body))[:320]
        if not item.alt_text: item.alt_text=item.title[:320]
        if not item.language: item.language="English"
    db.session.commit()

def get_or_create_user(name, email, password, role):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, password=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.flush()
    return user


def seed():
    db.create_all()
    migrate_schema()

    admin = get_or_create_user("Saloni", "admin@neurocms.local", "admin123", "Admin")
    editor = get_or_create_user("Demo Editor", "editor@neurocms.local", "editor123", "Editor")
    author = get_or_create_user("Demo Author", "author@neurocms.local", "author123", "Author")

    category_names = ["Technology", "Artificial Intelligence", "Education", "Development", "Business"]
    for name in category_names:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name, description=f"{name} related content"))
    db.session.commit()

    if Content.query.count() == 0:
        categories = {c.name: c for c in Category.query.all()}
        demo = [
            ("Introduction to Artificial Intelligence", "Artificial intelligence enables computer systems to learn patterns from data and support decisions. It is used in education, business, healthcare, automation and many other domains.", "Artificial Intelligence", "Published", "/static/visuals/ai.svg", admin),
            ("Python for Machine Learning", "Python provides a rich ecosystem for data processing, visualization and machine learning. Libraries such as scikit-learn support practical model development.", "Development", "Published", "/static/visuals/code.svg", admin),
            ("Headless CMS and REST APIs", "A headless CMS separates content management from presentation. REST APIs allow the same structured content to be consumed by websites, mobile applications and other clients.", "Technology", "Draft", "/static/visuals/api.svg", admin),
            ("AI in Education", "Artificial intelligence can support personalized learning, content organization, feedback and educational analytics when deployed with appropriate human oversight.", "Education", "Pending Review", "/static/visuals/education.svg", author),
        ]
        for title, body, category, status, image, owner in demo:
            item = Content(title=title, body=body, summary=ai.summarize(body), category=categories[category], status=status, views=12 if status == "Published" else 0, ai_score=ai.score(title, body), image_url=image, author_id=owner.id)
            if status == "Pending Review":
                item.submitted_at = datetime.utcnow()
            if status == "Published":
                item.published_at = datetime.utcnow()
            db.session.add(item)
            db.session.flush()
            db.session.add(ContentVersion(content_id=item.id, title=item.title, body=item.body, summary=item.summary, category_id=item.category_id, image_url=item.image_url, tags_json=json.dumps([tag.name for tag in item.tags]), version=1))
        db.session.commit()
    else:
        # Make old databases easier to demonstrate: ensure every existing content row has an owner.
        changed = False
        for item in Content.query.all():
            if item.author_id is None:
                item.author_id = admin.id
                changed = True
            if not item.image_url:
                item.image_url = "/static/visuals/ai.svg"
                changed = True
        if not Content.query.filter_by(status="Pending Review").first():
            category = Category.query.filter_by(name="Education").first()
            item = Content(
                title="AI in Education — Review Demo",
                body="Artificial intelligence can support personalized learning, content organization and educational analytics when used with human oversight.",
                summary="AI can support personalized learning and educational analytics with human oversight.",
                status="Pending Review",
                submitted_at=datetime.utcnow(),
                category=category,
                author_id=author.id,
                image_url="/static/visuals/education.svg",
                ai_score=82,
            )
            db.session.add(item)
            db.session.flush()
            db.session.add(ContentVersion(content_id=item.id, title=item.title, body=item.body, summary=item.summary, category_id=item.category_id, image_url=item.image_url, tags_json=json.dumps([tag.name for tag in item.tags]), version=1))
            changed = True
        if changed:
            db.session.commit()


with app.app_context():
    seed()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
