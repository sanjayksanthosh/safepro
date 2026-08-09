"""
Train the fake-review classifier.

Data: CMU Deceptive Opinion Spam corpus (op_spam_v1.4, 1600 hotel reviews,
half truthful / half deceptive). Downloaded once into data/ if missing.

Output: products/ml/fake_review_model.joblib — a Random Forest over
TF-IDF (text) + review statistics. Used by products/nlp.py at runtime.

Usage:
  python train_model.py
"""

import sys
import zipfile
from pathlib import Path

import joblib
import pandas as pd
import requests
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

sys.path.insert(0, str(Path(__file__).parent))

from products.ml.features import FEATURE_NAMES, review_features
from products.ml.model import MODEL_PATH, build_pipeline

DATASET_URL = "http://myleott.com/op_spam_v1.4.zip"
DATA_DIR = Path(__file__).parent / "data"
CORPUS_DIR = DATA_DIR / "op_spam_v1.4"


def ensure_dataset():
    if CORPUS_DIR.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archive = DATA_DIR / "op_spam_v1.4.zip"
    if not archive.exists():
        print(f"Downloading {DATASET_URL} ...")
        resp = requests.get(
            DATASET_URL, timeout=120,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        resp.raise_for_status()
        archive.write_bytes(resp.content)
    with zipfile.ZipFile(archive) as z:
        z.extractall(DATA_DIR)
    print("Dataset ready at", CORPUS_DIR)


def load_corpus(corpus_dir):
    texts, labels = [], []
    for polarity in ("positive_polarity", "negative_polarity"):
        base = corpus_dir / polarity
        for kind in ("truthful_from_Web", "truthful_from_TripAdvisor", "deceptive_from_MTurk"):
            kind_dir = base / kind
            if not kind_dir.exists():
                continue
            label = 1 if kind == "deceptive_from_MTurk" else 0
            for fold in sorted(kind_dir.iterdir()):
                if not fold.is_dir():
                    continue
                for txt in fold.glob("*.txt"):
                    texts.append(txt.read_text(encoding="utf-8", errors="ignore"))
                    labels.append(label)
    return texts, labels


def main():
    ensure_dataset()
    texts, labels = load_corpus(CORPUS_DIR)
    n_fake = sum(labels)
    print(f"Loaded {len(texts)} reviews ({n_fake} fake, {len(labels) - n_fake} genuine)")

    rows = []
    for t in texts:
        f = review_features(t)
        f["text"] = t
        rows.append(f)
    df = pd.DataFrame(rows)
    df["label"] = labels
    X = df[["text"] + FEATURE_NAMES]
    y = df["label"]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(build_pipeline(), X, y, cv=cv, scoring="accuracy")
    print("5-fold CV accuracy: %.2f%% (+/- %.2f%%)" % (scores.mean() * 100, scores.std() * 100))
    print("fold accuracies:", [f"{s * 100:.1f}%" for s in scores])

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    pipe = build_pipeline()
    pipe.fit(Xtr, ytr)
    pred = pipe.predict(Xte)
    acc = accuracy_score(yte, pred)
    p, r, f1, _ = precision_recall_fscore_support(yte, pred, average="binary")
    print(f"Holdout: accuracy={acc * 100:.1f}%  precision={p * 100:.1f}%  "
          f"recall={r * 100:.1f}%  F1={f1:.3f}")

    pipe.fit(X, y)  # final model trained on the full corpus
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)
    print("Saved model to", MODEL_PATH)


if __name__ == "__main__":
    main()
