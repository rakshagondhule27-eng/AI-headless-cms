# V5 Research Upgrade

V5 adds: a 50-sample balanced demonstration dataset, saved TF-IDF + Logistic Regression model, top-3 predictions, ML metrics display, audit logging, Admin-only deletion/audit endpoint, filtered TF-IDF search, model health endpoint, and cleaner AI analysis UI.

Important: the bundled dataset is for demonstration/testing. For final academic claims, use a larger domain-specific dataset with a documented source/licence, fixed train/test protocol, baselines, and repeatable experiments.

## Run
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python ml/train_model.py
python ml/compare_models.py
python app.py
```

Demo login: `admin@neurocms.local` / `admin123` (change before deployment).
