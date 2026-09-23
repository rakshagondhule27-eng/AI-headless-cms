import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, classification_report
import joblib

DATA_PATH = Path(__file__).parent / "dataset.json"
MODEL_PATH = Path(__file__).parent / "cms_classifier.joblib"
METRICS_PATH = Path(__file__).parent / "metrics.json"

def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    texts = [x["text"] for x in data]
    labels = [x["label"] for x in data]

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.25, random_state=42, stratify=labels
    )

    model = Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)),
        ("classifier", LogisticRegression(max_iter=1500))
    ])
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)
    accuracy = accuracy_score(y_test, pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, pred, average="weighted", zero_division=0
    )
    labels_order = list(model.classes_)
    cm = confusion_matrix(y_test, pred, labels=labels_order).tolist()

    metrics = {
        "model": "TF-IDF + Logistic Regression",
        "dataset_size": len(data),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "accuracy": round(float(accuracy), 4),
        "precision_weighted": round(float(precision), 4),
        "recall_weighted": round(float(recall), 4),
        "f1_weighted": round(float(f1), 4),
        "labels": labels_order,
        "confusion_matrix": cm,
        "classification_report": classification_report(
            y_test, pred, output_dict=True, zero_division=0
        )
    }
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps({
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision_weighted"],
        "recall": metrics["recall_weighted"],
        "f1": metrics["f1_weighted"],
        "model": str(MODEL_PATH)
    }, indent=2))

if __name__ == "__main__":
    main()
