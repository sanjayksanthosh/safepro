"""Model pipeline builder + lazy loader for live inference."""

import logging
from pathlib import Path

import joblib

from .features import FEATURE_NAMES, review_features

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "fake_review_model.joblib"

_model = None


def build_pipeline():
    """TF-IDF (text) + scaled statistics (numeric) -> Random Forest."""
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    numeric = FEATURE_NAMES
    return Pipeline([
        ("prep", ColumnTransformer([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 2), max_features=20000,
                sublinear_tf=True, min_df=1, lowercase=True,
            ), "text"),
            ("num", Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric),
        ])),
        ("clf", RandomForestClassifier(
            n_estimators=300, random_state=42, n_jobs=-1,
            class_weight="balanced",
        )),
    ])


def load_model():
    """Return the trained pipeline, or None if it hasn't been trained yet."""
    global _model
    if _model is None:
        if MODEL_PATH.exists():
            try:
                _model = joblib.load(MODEL_PATH)
                logger.info("Loaded fake-review model from %s", MODEL_PATH)
            except Exception as e:
                logger.warning("Failed to load model %s: %s", MODEL_PATH, e)
                _model = None
        else:
            logger.warning("No trained model at %s — falling back to rules", MODEL_PATH)
    return _model


def predict_fake_probability(text):
    """Probability (0..1) the review is fake, via the trained model.
    Returns None if no model is available."""
    model = load_model()
    if model is None:
        return None
    try:
        import pandas as pd
        row = review_features(text)
        row["text"] = text
        proba = model.predict_proba(pd.DataFrame([row]))[:, 1][0]
        return float(proba)
    except Exception as e:
        logger.warning("Model prediction failed: %s", e)
        return None
