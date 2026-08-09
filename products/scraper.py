"""
Scraper module.

Real mode (default): scrapes Amazon, Flipkart, and Myntra live with
Playwright (see scraper_playwright.py). Set SAFEPRO_DEMO=1 to fall back to
the fake-data generator below, e.g. for offline development.

Anti-bot caveat: these sites throttle/block scrapers, so individual runs can
come back partial or empty. Results are cached by the Django layer for 24h,
so live scraping only happens once per search term per day.
"""

import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Set SAFEPRO_DEMO=1 (env var) to fall back to the fake-data generator,
# e.g. when running without Playwright installed. Defaults to real scraping.
DEMO_MODE = os.environ.get("SAFEPRO_DEMO", "0") == "1"

SITES = ["amazon", "flipkart", "myntra"]

# ---------- DEMO MODE: fake data generator ----------

_GENUINE_TEMPLATES = [
    "Been using this for {n} weeks now and my skin feels so much better. No breakouts, absorbs quickly.",
    "Good product but a bit pricey for the size. Does the job though, no white cast.",
    "My dermatologist recommended something similar to this, works well under makeup.",
    "Decent SPF protection, lasted through a full day at the beach. Slight tacky feel at first.",
    "Not bad, but I've used better. Smells a bit strong for my liking. Would repurchase if on sale.",
]

_FAKE_TEMPLATES = [
    "BEST PRODUCT EVER!!! 5 STARS!!! BUY NOW!!! AMAZING!!!",
    "Excellent excellent excellent product very good very nice recommend to all",
    "Perfect perfect perfect changed my life 100% must buy",
    "great product great product great product",
]


def _make_review(genuine=True):
    if genuine:
        text = random.choice(_GENUINE_TEMPLATES).format(n=random.randint(2, 8))
        rating = round(random.uniform(3.0, 5.0), 1)
    else:
        text = random.choice(_FAKE_TEMPLATES)
        rating = 5.0
    return {
        "author": random.choice(["A.K.", "Priya S.", "verified_buyer_22", "user4471", "Meera N."]),
        "text": text,
        "star_rating": rating,
    }


def _demo_scrape_site(site, query):
    products = []
    for i in range(4):  # 4 products per site, per search
        base_price = random.randint(150, 1200)
        n_reviews = random.randint(10, 20)
        n_fake = random.randint(0, 4)  # a few products get some fake-looking reviews
        reviews = [_make_review(genuine=False) for _ in range(n_fake)] + \
                  [_make_review(genuine=True) for _ in range(n_reviews - n_fake)]
        random.shuffle(reviews)

        products.append({
            "name": f"{query.title()} {random.choice(['Gel', 'Lotion', 'Cream', 'Spray'])} SPF{random.choice([30, 50, 60])}",
            "source_site": site,
            "url": f"https://{site}.example.com/product/{random.randint(10000,99999)}",
            "price": float(base_price),
            "description": f"A {query} formulated for daily use, lightweight and non-greasy.",
            "image_url": "",
            "rating": round(random.uniform(3.2, 4.8), 1),
            "reviews": reviews,
        })
    return products


# ---------- REAL MODE: Playwright scraper (Amazon / Flipkart / Myntra) ----------

def _real_scrape_site(site, query, max_items=3, on_progress=None):
    """Live scrape via Playwright. Returns product dicts in pipeline format
    (name, source_site, url, price, description, image_url, rating, reviews)."""
    from .scraper_playwright import scrape_site
    return scrape_site(site, query, max_items=max_items, on_progress=on_progress)


# ---------- Public entry point ----------

def _scrape_one_site(site, query, max_items=3, on_progress=None):
    if DEMO_MODE:
        if on_progress:
            on_progress(f"Generating demo data for {site}...", "progress")
        return _demo_scrape_site(site, query)
    return _real_scrape_site(site, query, max_items=max_items, on_progress=on_progress)


def scrape_all_sites(query, on_progress=None):
    """Returns a list of product dicts (each with a 'reviews' list inside)
    from every site, for the given search term.

    The sites are scraped in parallel (one thread each) to cut wall-clock
    time down from "sum of all three" to "slowest of the three".

    on_progress(msg, detail) is forwarded to each site's scraper so a caller
    can surface live progress to the user."""
    all_products = []
    with ThreadPoolExecutor(max_workers=len(SITES)) as executor:
        futures = {
            executor.submit(_scrape_one_site, site, query, on_progress=on_progress): site
            for site in SITES
        }
        for future in as_completed(futures):
            site = futures[future]
            try:
                products = future.result()
                all_products.extend(products)
                logger.info("Site %s returned %d products", site, len(products))
            except Exception:
                logger.exception("Site %s scrape failed", site)
    return all_products
