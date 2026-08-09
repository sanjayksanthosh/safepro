from rest_framework import serializers
from .models import Product, Review


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "author", "text", "star_rating", "sentiment_score", "fake_probability"]


class ProductSerializer(serializers.ModelSerializer):
    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "source_site", "url", "price", "description",
            "image_url", "rating", "trust_score", "avg_sentiment",
            "genuine_review_pct", "reviews",
        ]
