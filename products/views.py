import logging
import threading
from datetime import timedelta

from django.db import close_old_connections
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SearchQuery, Product, Review
from .scraper import scrape_all_sites
from .nlp import analyze_reviews, compute_trust_score
from .serializers import ProductSerializer

logger = logging.getLogger(__name__)

CACHE_HOURS = 24  # how long before we consider cached results "stale"
STALE_JOB_MINUTES = 15  # pending job older than this is treated as dead

# Guards against double-starting a scrape for the same term inside one process.
_job_lock = threading.Lock()

# Live progress for in-flight jobs: {search_query_id: {"message": str}}
_PROGRESS = {}


def _fresh_search_query(term):
    existing = SearchQuery.objects.filter(term=term).first()
    if existing and (timezone.now() - existing.last_scraped_at) < timedelta(hours=CACHE_HOURS):
        return existing, True
    return existing, False


def _is_stale(search_query):
    if search_query.status not in ("pending", "processing"):
        return False
    age = timezone.now() - search_query.last_scraped_at
    return age > timedelta(minutes=STALE_JOB_MINUTES)


def _scrape_and_save(search_query, query_text):
    """Scrape -> NLP -> persist. Runs in a background thread."""
    def report(message, detail=None):
        _PROGRESS[search_query.id] = {"message": message}

    try:
        _PROGRESS[search_query.id] = {"message": "Starting scrape..."}
        search_query.products.all().delete()  # replace old data for this term
        scraped_products = scrape_all_sites(query_text, on_progress=report)

        _PROGRESS[search_query.id] = {"message": "Analyzing reviews and scoring..."}
        prices = [p["price"] for p in scraped_products if p.get("price")]
        median_price = sorted(prices)[len(prices) // 2] if prices else None

        for p in scraped_products:
            analyzed_reviews = analyze_reviews(p["reviews"])
            trust_score, avg_sentiment, genuine_pct = compute_trust_score(
                analyzed_reviews, p["price"], median_price
            )

            product = Product.objects.create(
                search_query=search_query,
                name=p["name"],
                source_site=p["source_site"],
                url=p["url"],
                price=p["price"],
                description=p["description"],
                image_url=p.get("image_url", ""),
                rating=p.get("rating"),
                trust_score=trust_score,
                avg_sentiment=avg_sentiment,
                genuine_review_pct=genuine_pct,
            )
            for r in analyzed_reviews:
                Review.objects.create(
                    product=product,
                    author=r.get("author", ""),
                    text=r["text"],
                    star_rating=r.get("star_rating"),
                    sentiment_score=r["sentiment_score"],
                    fake_probability=r["fake_probability"],
                )
        search_query.status = "ready"
        search_query.error = ""
        search_query.save()
        logger.info("Finished scraping '%s': %d products", query_text, len(scraped_products))
    except Exception as e:
        logger.exception("Scrape failed for '%s'", query_text)
        search_query.status = "error"
        search_query.error = str(e)
        search_query.save()
    finally:
        _PROGRESS.pop(search_query.id, None)
        # threads use their own DB connection; close it when done
        close_old_connections()


def _start_background_job(search_query, query_text):
    thread = threading.Thread(
        target=_scrape_and_save,
        args=(search_query, query_text),
        daemon=True,
        name=f"scrape-{search_query.id}",
    )
    thread.start()


def _status_response(search_query):
    return Response({
        "cached": False,
        "processing": search_query.status in ("pending", "processing"),
        "status": search_query.status,
        "error": search_query.error or None,
        "progress": (_PROGRESS.get(search_query.id) or {}).get("message"),
    })


@api_view(["GET"])
def search(request):
    query_text = request.GET.get("q", "").strip().lower()
    if not query_text:
        return Response({"error": "Provide a search term with ?q="}, status=400)

    existing, is_fresh = _fresh_search_query(query_text)

    if existing and is_fresh and existing.status == "ready":
        products = existing.products.all().order_by("-trust_score")
        return Response({
            "cached": True,
            "query": query_text,
            "results": ProductSerializer(products, many=True).data,
        })

    # A stale in-flight job (e.g. the worker process died) must not block
    # forever — reset it so the next search restarts the scrape.
    if existing and _is_stale(existing):
        logger.warning("Resetting stale '%s' job (status=%s)", query_text, existing.status)
        existing.status = "error"
        existing.error = "Previous attempt timed out. Retry."
        existing.save()

    if existing and existing.status in ("pending", "processing"):
        return _status_response(existing)

    # Kick off a fresh scrape in the background and return immediately.
    with _job_lock:
        existing, _ = _fresh_search_query(query_text)
        if existing and not _is_stale(existing) and existing.status in ("pending", "processing"):
            return _status_response(existing)
        search_query, _ = SearchQuery.objects.get_or_create(term=query_text)
        search_query.status = "pending"
        search_query.error = ""
        search_query.save()

    _start_background_job(search_query, query_text)
    return _status_response(search_query)


@api_view(["GET"])
def product_detail(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({"error": "Not found"}, status=404)
    return Response(ProductSerializer(product).data)
