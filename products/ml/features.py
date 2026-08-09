"""Feature extraction shared between training and live inference."""

import re
from nltk.sentiment import SentimentIntensityAnalyzer

_sia = SentimentIntensityAnalyzer()

_FIRST_PERSON = {"i", "me", "my", "mine", "we", "our", "ours", "us"}


def clean_text(text):
    text = re.sub(r"<.*?>", " ", text)                      # strip HTML
    text = re.sub(r"[^a-zA-Z0-9\s.,!?']", " ", text)        # strip symbols/emoji
    return re.sub(r"\s+", " ", text).strip()


def review_features(text, sentiment=None):
    """Numeric, text-derived features. Every feature here must be computable
    from the review text alone so the same function works in training
    (CMU corpus has no star ratings) and in live inference."""
    if sentiment is None:
        sentiment = _sia.polarity_scores(clean_text(text))["compound"]

    words = clean_text(text).split()
    n = max(len(words), 1)
    lower = [w.lower() for w in words]

    first_person = sum(1 for w in lower if w in _FIRST_PERSON)
    caps = sum(1 for w in words if w.isupper() and len(w) > 2)
    exclam = text.count("!")
    question = text.count("?")
    punct = sum(1 for c in text if c in "!?,.;:")
    unique = len(set(lower))

    return {
        "sentiment": sentiment,
        "length_words": len(words),
        "length_chars": len(text),
        "exclamation_ratio": exclam / n,
        "question_ratio": question / n,
        "caps_ratio": caps / n,
        "punctuation_ratio": punct / max(len(text), 1),
        "unique_word_ratio": unique / n,
        "first_person_ratio": first_person / n,
    }


FEATURE_NAMES = sorted(review_features("test").keys())
