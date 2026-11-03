from django.test import SimpleTestCase
from unittest.mock import patch

from products.nlp import (
    _has_repetition,
    analyze_reviews,
    clean_text,
    compute_trust_score,
    fake_probability,
    sentiment_score,
)


class CleanTextTests(SimpleTestCase):
    def test_strips_html_and_collapses_whitespace(self):
        raw = "  <b>Great</b>   product\n\nfor   you  "
        self.assertEqual(clean_text(raw), "Great product for you")

    def test_strips_symbols_not_on_the_allow_list(self):
        self.assertEqual(clean_text("Hello!!! 100%"), "Hello!!! 100")


class SentimentTests(SimpleTestCase):
    def test_positive_text_scores_above_zero(self):
        self.assertGreater(sentiment_score("This product is amazing and works perfectly."), 0)

    def test_negative_text_scores_below_zero(self):
        self.assertLess(sentiment_score("Terrible quality, broke after one day. Do not buy."), 0)


class RepetitionTests(SimpleTestCase):
    def test_detects_repeated_word(self):
        self.assertTrue(_has_repetition("great great great product".split()))

    def test_detects_repeated_phrase(self):
        self.assertTrue(_has_repetition("buy now buy now buy now".split()))

    def test_genuine_review_is_not_flagged(self):
        self.assertFalse(
            _has_repetition("I have used this moisturiser for three weeks and it works well".split())
        )


class FakeProbabilityTests(SimpleTestCase):
    @patch('products.nlp.predict_fake_probability', lambda _text: None)
    def test_shouting_hype_and_short_text_score_high(self, _mock=None):
        prob = fake_probability(
            "AMAZING!!! BEST EVER!!! MUST BUY NOW!!!",
            5,
            sentiment_score("AMAZING!!! BEST EVER!!! MUST BUY NOW!!!"),
            [],
        )
        self.assertGreaterEqual(prob, 0.5)

    @patch('products.nlp.predict_fake_probability', lambda _text: None)
    def test_genuine_detailed_review_scores_lower(self, _mock=None):
        text = (
            "I have been using this face wash for about six weeks. It lathers well, "
            "does not dry out my skin, and the fragrance is mild. Packaging could be "
            "better but overall I am happy with the purchase."
        )
        prob = fake_probability(text, 4, sentiment_score(text), [])
        self.assertLess(prob, 0.5)

    @patch('products.nlp.predict_fake_probability', lambda _text: None)
    def test_near_duplicate_reviews_are_flagged(self, _mock=None):
        original = "Great product, love it, highly recommended to all."
        duplicate = "Great product, love it, highly recommended to all!"
        score = fake_probability(duplicate, 5, sentiment_score(duplicate), [original])
        self.assertGreaterEqual(score, 0.5)

    @patch('products.nlp.predict_fake_probability', lambda _text: None)
    def test_sentiment_rating_mismatch_is_flagged(self, _mock=None):
        text = "Terrible, broke after one use, very disappointing."
        prob = fake_probability(text, 5, sentiment_score(text), [])
        self.assertGreaterEqual(prob, 0.5)

    @patch('products.nlp.predict_fake_probability', lambda _text: None)
    def test_probability_is_bounded(self, _mock=None):
        prob = fake_probability("x", 5, 1.0, [])
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)


class AnalyzeReviewsTests(SimpleTestCase):
    def test_adds_sentiment_and_fake_probability(self):
        reviews = [
            {"author": "a", "text": "Excellent quality, fast delivery.", "star_rating": 5},
            {"author": "b", "text": "Bad, stopped working.", "star_rating": 1},
        ]
        result = analyze_reviews(reviews)

        for review in result:
            self.assertIn("sentiment_score", review)
            self.assertIn("fake_probability", review)
            self.assertIsInstance(review["sentiment_score"], float)
            self.assertIsInstance(review["fake_probability"], float)


class TrustScoreTests(SimpleTestCase):
    def test_empty_reviews_return_zero_tuple(self):
        self.assertEqual(compute_trust_score([], 100, 100), (0, 0, 0))

    def test_genuine_reviews_produce_positive_trust(self):
        reviews = [
            {
                "text": "I have used this for a month and it works well for daily use.",
                "star_rating": 4,
                "sentiment_score": 0.6,
                "fake_probability": 0.1,
            },
            {
                "text": "Solid build quality and good value for money.",
                "star_rating": 4,
                "sentiment_score": 0.5,
                "fake_probability": 0.2,
            },
        ]
        trust, sentiment, genuine_pct = compute_trust_score(reviews, 500, 450)

        self.assertGreater(trust, 50)
        self.assertGreaterEqual(genuine_pct, 99.0)
        self.assertAlmostEqual(sentiment, 0.55, places=2)

    def test_suspiciously_cheap_price_lowers_trust(self):
        reviews = [
            {
                "text": "Looks fine and works as expected.",
                "star_rating": 4,
                "sentiment_score": 0.4,
                "fake_probability": 0.1,
            }
        ]
        trust_full, _, _ = compute_trust_score(reviews, 450, 450)
        trust_cheap, _, _ = compute_trust_score(reviews, 100, 450)

        self.assertLess(trust_cheap, trust_full)

    def test_all_fake_reviews_give_zero_genuine_share(self):
        reviews = [
            {
                "text": "AMAZING MUST BUY",
                "star_rating": 5,
                "sentiment_score": 0.9,
                "fake_probability": 0.9,
            }
        ]
        _, _, genuine_pct = compute_trust_score(reviews, 500, 500)
        self.assertEqual(genuine_pct, 0.0)
