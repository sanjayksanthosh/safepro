"""
NLP / analysis pipeline.

Two things happen to every review:
1. Sentiment analysis (NLTK VADER) - how positive/negative is the text?
2. Fake-review scoring - a rule-based heuristic strengthened with signals from
   the fake-review literature (shouting, hype language, repetition, short
   generic text, rating/sentiment mismatch, near-duplicates), blended with a
   trained Random Forest (products/ml/) as a complementary stylistic signal.

Train the model once with:  python train_model.py
"""

import logging
import re
from collections import Counter

from nltk.sentiment import SentimentIntensityAnalyzer

from .ml.model import predict_fake_probability

logger = logging.getLogger(__name__)

_sia = SentimentIntensityAnalyzer()

# Blend weights: how much the trained model contributes vs the rules.
# The model is trained on hotel reviews (CMU corpus), so on out-of-domain
# cosmetic reviews it is only a mild adjustment; the rules carry the signal.
MODEL_WEIGHT = 0.4

# Threshold above which a review is treated as fake-looking.
FAKE_THRESHOLD = 0.5

# Generic superlatives / hype language common in fake reviews but rare in
# specific, honest ones.
_HYPE_WORDS = [
    "amazing", "awesome", "superb", "wonderful", "fantastic", "incredible",
    "perfect", "best ever", "number one", "100%", "must buy", "buy now",
    "recommend to all", "recommended to all", "love it", "love this",
    "great product", "very good product", "trusted", "genuine product",
    "original product", "authentic product",
]


def clean_text(text):
    text = re.sub(r"<.*?>", " ", text)          # strip HTML
    text = re.sub(r"[^a-zA-Z0-9\s.,!?']", " ", text)  # strip weird symbols/emoji
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sentiment_score(text):
    """Returns a float from -1 (very negative) to 1 (very positive)."""
    cleaned = clean_text(text)
    return _sia.polarity_scores(cleaned)["compound"]


def _has_repetition(words):
    """Detect anaphoric spam like 'great product great product great product'
    or 'excellent excellent excellent'."""
    lower = [w.lower() for w in words]
    if not lower:
        return False
    most = Counter(lower).most_common(1)[0]
    if most[1] >= 3:                       # same word 3+ times
        return True
    for size in (2, 3, 4):                 # same phrase repeated
        if len(lower) < size * 2:
            continue
        grams = [tuple(lower[i:i + size]) for i in range(len(lower) - size + 1)]
        if grams and grams[0] in grams[1:] and grams.count(grams[0]) >= 2:
            return True
    return False


def fake_probability(text, star_rating, sentiment, all_review_texts):
    """
    0 = looks genuine, 1 = looks fake.

    Rule-based red flags (from the fake-review literature):
    - all-caps shouting / excessive punctuation
    - hype words and superlative-heavy, low-detail language
    - within-review repetition (anaphora)
    - very short, generic reviews
    - sentiment-rating mismatch
    - near-duplicate text vs other reviews on the same product

    Blended with the trained ML model's probability.
    """
    score = 0.0
    cleaned = clean_text(text)
    words = cleaned.split()
    n = max(len(words), 1)
    lowered = text.lower()

    # Red flag 1: shouting / excessive punctuation
    exclamations = text.count("!")
    caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 2) / n
    if exclamations >= 2 or caps_ratio >= 0.4:
        score += 0.3

    # Red flag 2: hype-heavy, low-detail language
    hype_hits = sum(1 for h in _HYPE_WORDS if h in lowered)
    if hype_hits >= 2:
        score += 0.3
    elif hype_hits == 1:
        score += 0.1

    # Red flag 3: within-review repetition (anaphora)
    if _has_repetition(words):
        score += 0.3

    # Red flag 4: too short to be a specific, honest opinion
    if n < 8:
        score += 0.2

    # Red flag 5: sentiment/rating mismatch
    if star_rating is not None:
        if star_rating >= 4 and sentiment < -0.2:
            score += 0.3
        if star_rating <= 2 and sentiment > 0.4:
            score += 0.3

    # Red flag 6: near-duplicate of another review on this product
    for other in all_review_texts:
        if other == text:
            continue
        overlap = _word_overlap_ratio(cleaned, clean_text(other))
        if overlap > 0.8:
            score += 0.3
            break

    score = min(score, 1.0)

    # Blend in the trained ML model's view (complementary stylistic signal)
    ml_prob = predict_fake_probability(text)
    if ml_prob is not None:
        score = MODEL_WEIGHT * ml_prob + (1 - MODEL_WEIGHT) * score
    else:
        logger.debug("ML model unavailable — rule-based score only")

    return min(score, 1.0)


def _word_overlap_ratio(a, b):
    wa, wb = Counter(a.lower().split()), Counter(b.lower().split())
    if not wa or not wb:
        return 0
    overlap = sum((wa & wb).values())
    return overlap / max(sum(wa.values()), sum(wb.values()))


def analyze_reviews(reviews):
    """Takes a list of {author, text, star_rating} dicts, returns the same
    list with sentiment_score and fake_probability added to each."""
    all_texts = [r["text"] for r in reviews]
    for r in reviews:
        r["sentiment_score"] = sentiment_score(r["text"])
        r["fake_probability"] = fake_probability(
            r["text"], r.get("star_rating"), r["sentiment_score"], all_texts
        )
    return reviews


def compute_trust_score(reviews, price, category_median_price):
    """
    Combines review authenticity + sentiment + price sanity into one
    0-100 trust score for a product.
    """
    if not reviews:
        return 0, 0, 0

    genuine_reviews = [r for r in reviews if r["fake_probability"] < FAKE_THRESHOLD]
    genuine_pct = 100 * len(genuine_reviews) / len(reviews)

    avg_sentiment = sum(r["sentiment_score"] for r in genuine_reviews) / len(genuine_reviews) \
        if genuine_reviews else 0

    # price sanity: suspiciously cheap (common counterfeit signal) hurts the score
    price_score = 1.0
    if category_median_price and price:
        ratio = price / category_median_price
        if ratio < 0.5:      # less than half the median price = suspicious
            price_score = 0.4
        elif ratio < 0.7:
            price_score = 0.7

    trust_score = (
        (genuine_pct / 100) * 40 +
        ((avg_sentiment + 1) / 2) * 40 +
        price_score * 20
    )
    return round(trust_score, 1), round(avg_sentiment, 2), round(genuine_pct, 1)
