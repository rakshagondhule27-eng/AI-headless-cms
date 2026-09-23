import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

BASE = Path(__file__).parent
data = json.loads((BASE/"dataset.json").read_text(encoding="utf-8"))
texts=[x["text"] for x in data]; labels=[x["label"] for x in data]
Xtr,Xte,ytr,yte=train_test_split(texts,labels,test_size=.25,random_state=42,stratify=labels)

models={
"TF-IDF + Logistic Regression": LogisticRegression(max_iter=1500),
"TF-IDF + Linear SVM": LinearSVC()
}
results={}
for name, clf in models.items():
    pipe=Pipeline([("tfidf",TfidfVectorizer(stop_words="english",ngram_range=(1,2))),("classifier",clf)])
    pipe.fit(Xtr,ytr)
    pred=pipe.predict(Xte)
    p,r,f,_=precision_recall_fscore_support(yte,pred,average="weighted",zero_division=0)
    results[name]={
        "accuracy":round(float(accuracy_score(yte,pred)),4),
        "precision_weighted":round(float(p),4),
        "recall_weighted":round(float(r),4),
        "f1_weighted":round(float(f),4)
    }
(BASE/"comparison.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
print(json.dumps(results,indent=2))
