import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_parses():
    ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))


def test_ai_engine_parses():
    ast.parse((ROOT / "ai_engine.py").read_text(encoding="utf-8"))


def test_ml_scripts_parse():
    for name in ("train_model.py", "compare_models.py"):
        ast.parse((ROOT / "ml" / name).read_text(encoding="utf-8"))


def test_required_project_files_exist():
    required = [
        "app.py",
        "ai_engine.py",
        "requirements.txt",
        "README.md",
        "ARCHITECTURE.md",
        "ml/dataset.json",
        "ml/train_model.py",
        "ml/compare_models.py",
        "templates/base.html",
        "templates/api_docs.html",
        "templates/intelligence.html",
        "templates/api_keys.html",
        "templates/architecture.html",
        "templates/research.html",
        "static/app.js",
        "static/style.css",
    ]
    for item in required:
        assert (ROOT / item).exists(), item


def test_visual_library_exists():
    visuals = ["ai.svg", "code.svg", "api.svg", "education.svg", "business.svg"]
    for item in visuals:
        assert (ROOT / "static" / "visuals" / item).exists(), item


def test_submission_docs_exist():
    docs = [
        "PROJECT_STATUS.md",
        "docs/SUBMISSION_CHECKLIST.md",
        "docs/SEMINAR_CONTENT.md",
        "docs/VIVA_QA.md",
        "docs/RESEARCH_REFERENCES.md",
    ]
    for item in docs:
        assert (ROOT / item).exists(), item
