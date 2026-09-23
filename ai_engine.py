import re
from collections import Counter
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

class AIEngine:
    STOP = set('the a an and or but if then is are was were be been being to of in on for with by from as at this that these those it its into about over under after before than also can will would should could has have had do does did i you he she they we them their our your my me his her not very more most using use used users content system data'.split())
    TRAIN = [
        ('artificial intelligence machine learning deep learning neural networks nlp natural language processing generative ai', 'Artificial Intelligence'),
        ('python programming software api backend development javascript html css web application', 'Development'),
        ('student education university learning study classroom examination teaching', 'Education'),
        ('business finance marketing startup management entrepreneurship sales', 'Business'),
        ('database sql cloud api cybersecurity technology servers software', 'Technology'),
    ]
    def __init__(self):
        self.model_path = Path(__file__).resolve().parent / 'ml' / 'cms_classifier.joblib'
        self.trained_model = None
        if self.model_path.exists():
            try:
                import joblib
                self.trained_model = joblib.load(self.model_path)
            except Exception:
                self.trained_model = None
        if self.trained_model is None:
            texts, labels = zip(*self.TRAIN)
            self.vectorizer = TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)
            X = self.vectorizer.fit_transform(texts)
            self.classifier = LogisticRegression(max_iter=1000, random_state=42)
            self.classifier.fit(X, labels)
        else:
            self.vectorizer = self.trained_model.named_steps['tfidf']
            self.classifier = self.trained_model.named_steps['classifier']

    def keywords(self, text, n=8):
        words = re.findall(r'[A-Za-z][A-Za-z0-9-]{2,}', text.lower())
        words = [w for w in words if w not in self.STOP]
        return [w for w, _ in Counter(words).most_common(n)]

    def summarize(self, text, n=3):
        if not text.strip(): return ''
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if len(sentences) <= n: return text.strip()
        keys = set(self.keywords(text, 12))
        scored=[]
        for i,s in enumerate(sentences):
            words=re.findall(r'[a-zA-Z]+',s.lower())
            score=sum(w in keys for w in words)/(len(words) or 1)
            scored.append((score,i,s))
        best=sorted(scored, reverse=True)[:n]
        return ' '.join(x[2] for x in sorted(best,key=lambda x:x[1]))

    def _X(self,text): return self.vectorizer.transform([text])
    def classify(self, text):
        if not text.strip(): return 'General'
        return self.classifier.predict(self._X(text))[0]

    def probabilities(self, text):
        if not text.strip() or not hasattr(self.classifier, 'predict_proba'):
            return []
        probs=self.classifier.predict_proba(self._X(text))[0]
        pairs=sorted(zip(self.classifier.classes_, probs), key=lambda x:x[1], reverse=True)
        return [{'category':label,'confidence':round(float(p)*100,1)} for label,p in pairs]

    def confidence(self, text):
        p=self.probabilities(text)
        return p[0]['confidence'] if p else 0.0

    def score(self,title,body):
        words=len(body.split()); keys=len(self.keywords(body))
        title_score=1 if 3<=len(title.split())<=12 else .5
        return round((25*title_score)+(45*min(1,words/100))+(30*min(1,keys/6)),1)

    def readability(self, text):
        words=re.findall(r'\b\w+\b',text)
        sentences=max(1,len(re.findall(r'[.!?]+',text)))
        syllables=sum(max(1,len(re.findall(r'[aeiouy]+',w.lower()))) for w in words)
        if not words:return 0
        value=206.835-1.015*(len(words)/sentences)-84.6*(syllables/len(words))
        return round(max(0,min(100,value)),1)

    def generate(self,t,mode):
        k=self.keywords(t)
        if mode=='title': return {'title':t.title()+' — A Practical Guide','keywords':k}
        if mode=='summary': return {'summary':f'{t} is an important topic with practical applications. It covers core concepts, benefits, implementation considerations and measurable outcomes.','keywords':k}
        if mode=='tags': return {'tags':k or ['technology','innovation','learning']}
        body=f'{t} is an important area in modern technology with practical applications.\n\nThe topic can be understood through its fundamentals, real-world use cases, implementation methods and measurable results.\n\nA strong implementation should use suitable data, clear requirements and meaningful evaluation metrics. It should also consider usability, security and responsible use.'
        return {'title':t.title()+' — A Practical Guide','summary':self.summarize(body),'body':body,'keywords':k}

    def recommend(self, target, candidates, limit=5):
        if not candidates:return []
        texts=[target.title+' '+target.body]+[x.title+' '+x.body for x in candidates]
        vec=TfidfVectorizer(stop_words='english',ngram_range=(1,2))
        M=vec.fit_transform(texts)
        sims=cosine_similarity(M[0:1],M[1:])[0]
        ranked=sorted(zip(sims,candidates),key=lambda x:x[0],reverse=True)
        return [(x[1],round(float(x[0])*100,1)) for x in ranked[:limit]]
