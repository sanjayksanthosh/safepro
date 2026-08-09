from django.db import models


class SearchQuery(models.Model):
    """Remembers what someone searched for, so we can serve cached
    results instantly next time instead of scraping again."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("error", "Error"),
    ]
    term = models.CharField(max_length=255, db_index=True)
    last_scraped_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ready")
    error = models.TextField(blank=True, default="")

    def __str__(self):
        return self.term


class Product(models.Model):
    """One product listing from one site (e.g. a specific sunscreen on Nykaa)."""
    search_query = models.ForeignKey(SearchQuery, related_name="products", on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    source_site = models.CharField(max_length=50)     # "amazon" / "nykaa" / "flipkart"
    url = models.URLField(max_length=1000, blank=True)
    price = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    rating = models.FloatField(null=True, blank=True)          # site's own star rating
    trust_score = models.FloatField(default=0)                 # our computed score, 0-100
    avg_sentiment = models.FloatField(default=0)                # -1 to 1
    genuine_review_pct = models.FloatField(default=0)           # 0-100
    scraped_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.source_site})"


class Review(models.Model):
    """A single review scraped for a product, with our NLP analysis attached."""
    product = models.ForeignKey(Product, related_name="reviews", on_delete=models.CASCADE)
    author = models.CharField(max_length=200, blank=True)
    text = models.TextField()
    star_rating = models.FloatField(null=True, blank=True)
    sentiment_score = models.FloatField(default=0)     # -1 (negative) to 1 (positive)
    fake_probability = models.FloatField(default=0)    # 0 (looks genuine) to 1 (looks fake)

    def __str__(self):
        return self.text[:50]
