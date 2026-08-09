"""
Real-site scraper (Playwright).

Replaces the demo generator with live data from Amazon / Flipkart / Myntra.
Best-effort: all three sites change their HTML often and use anti-bot
protection (captchas, IP throttling), so a scrape may come back partial or
empty on any given run. The Django layer caches results for 24h, so live
scraping only happens once per search term per day.

Setup (once):
  pip install playwright playwright-stealth
  python -m playwright install chromium

Note: Myntra's CDN blocks Playwright in headless mode, so it launches a
visible browser window. Amazon/Flipkart run headless.
"""

import logging
import re
import time
import urllib.parse

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

DEFAULT_MAX_PER_SITE = 3   # product pages per site, per search
MIN_DELAY, MAX_DELAY = 0.6, 1.2  # seconds between page loads
MAX_REVIEWS_PER_PRODUCT = 10

SITES = {
    "amazon": {
        "domain": "https://www.amazon.in",
        "search_url": "https://www.amazon.in/s?k={query}",
        "product_link": 'div[data-component-type="s-search-result"] a.a-link-normal',
        "name": "#productTitle",
        "price": 'span.a-price > span.a-offscreen',
        "description": "#productDescription, #feature-bullets",
        "review_block": 'div[data-hook="review"]',
        "review_text": 'div[data-hook="reviewRichContentContainer"]',
        "review_rating": 'i[data-hook="review-star-rating"] span',
        "captcha_markers": ["captcha", "Enter the characters", "robot check"],
        "url_marker": "/dp/",
    },
    "flipkart": {
        "domain": "https://www.flipkart.com",
        "search_url": "https://www.flipkart.com/search?q={query}",
        "product_link": 'a[href*="/p/"]',
        "name": "h1, span.B_NUCI",
        "price": "div.Nx9bqj, div._30jeq3",
        "description": "div._3k-BhJ, div._2-oMuo",
        "review_block": "div._1AtVbE",
        "review_text": "p.z9E0IG",
        "review_rating": "div._3LWZlK",
        "captcha_markers": ["captcha", "puzzle"],
        "url_marker": "/p/",
        "price_pattern": "₹[0-9,]+",
        "reviews_page": True,
    },
    "myntra": {
        "domain": "https://www.myntra.com",
        "search_url": "https://www.myntra.com/{query}?rawQuery={query}",
        "product_link": '#desktopSearchResults a[data-refreshpage="true"]',
        "name": "h1.pdp-name, span.base-name",
        "price": "span.pdp-final-price, span.pdp-price strong",
        "description": "div.pdp-description-container",
        "review_block": "div.user-review-main",
        "review_text": "div.user-review-reviewTextWrapper",
        "review_rating": "span.user-review-starRating",
        "captcha_markers": ["captcha", "unusual traffic"],
        "url_marker": "/buy",
        "force_headed": True,
    },
}


# ---------------------------------------------------------------------------
# Low-level page helpers
# ---------------------------------------------------------------------------

def first_text(page, selectors: str, timeout_ms: int = 5000) -> str:
    for sel in selectors.split(","):
        sel = sel.strip()
        try:
            txt = page.locator(sel).first.inner_text(timeout=timeout_ms).strip()
            if txt:
                return txt
        except Exception:
            continue
    return ""


def match_price(page, pattern: str) -> str:
    """Text-based price fallback for sites with obfuscated markup (Flipkart)."""
    try:
        matches = page.locator("div, span").evaluate_all(
            """(els, pat) => {
                const re = new RegExp('^' + pat + '$');
                return els.map(e => (e.innerText || '').trim())
                         .filter(t => t && re.test(t));
            }""",
            pattern,
        )
        if matches:
            return matches[0]
    except Exception:
        pass
    return ""


def looks_like_captcha(page, markers) -> bool:
    try:
        title = (page.title() or "").lower()
        body = (page.locator("body").inner_text(timeout=2000) or "")[:3000].lower()
    except Exception:
        return False
    haystack = f"{title} {body}"
    return any(m.lower() in haystack for m in markers)


# ---------------------------------------------------------------------------
# URL discovery + product scraping
# ---------------------------------------------------------------------------

def discover_urls(page, cfg: dict, query: str, max_items: int) -> list[str]:
    url = cfg["search_url"].format(query=urllib.parse.quote_plus(query))
    logger.info("Searching: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Wait for actual result tiles to render instead of sleeping blind.
    try:
        page.wait_for_selector(cfg["product_link"], timeout=15000)
    except Exception:
        pass
    time.sleep(1.0)

    if looks_like_captcha(page, cfg["captcha_markers"]):
        logger.warning("Possible captcha/block on search page — trying anyway.")

    page.mouse.wheel(0, 3000)
    time.sleep(0.8)

    urls, seen = [], set()
    for link in page.locator(cfg["product_link"]).all():
        try:
            href = link.get_attribute("href")
        except Exception:
            continue
        if not href or cfg["url_marker"] not in href:
            continue
        if not href.startswith("http"):
            href = cfg["domain"] + "/" + href.lstrip("/")
        base = href.split("?")[0].split("#")[0]
        if cfg["url_marker"].endswith("/"):
            key = base.split(cfg["url_marker"])[1].split("/")[0]
        else:
            key = base.split(cfg["url_marker"])[0].rstrip("/").split("/")[-1]
        if key not in seen:
            seen.add(key)
            urls.append(base)
        if len(urls) >= max_items:
            break
    logger.info("Found %d product URLs", len(urls))
    return urls


def scrape_reviews_page(page, cfg: dict, url: str, output: dict):
    """Flipkart loads reviews on a separate /product-reviews/ page. Go there
    and extract review cards directly from the rendered DOM."""
    slug = url.split(cfg["url_marker"])[0]
    pid = url.split(cfg["url_marker"])[1].split("/")[0]
    reviews_url = f"{slug}/product-reviews/{pid}"
    logger.info("Reviews page: %s", reviews_url)

    try:
        page.goto(reviews_url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector("span.css-1jxf684", timeout=15000)
        except Exception:
            pass
        time.sleep(0.8)
    except Exception as e:
        logger.warning("Failed to load reviews page %s: %s", reviews_url, e)
        return

    cards = []
    try:
        cards = page.evaluate(
            """() => {
                const out = [];
                for (const s of document.querySelectorAll('span.css-1jxf684')) {
                    const body = (s.innerText || '').trim();
                    if (!body || /^(more|less|read more)$/i.test(body)) continue;
                    let card = s.parentElement;
                    for (let i = 0; i < 12 && card; i++) {
                        const first = ((card.innerText || '').trim().split('\\n')[0]).trim();
                        if (/^\\d+(\\.\\d+)?$/.test(first)) break;
                        card = card.parentElement;
                    }
                    if (!card) continue;
                    const lines = (card.innerText || '').trim().split('\\n').map(x => x.trim());
                    const rating = parseFloat(lines[0]);
                    out.push({ text: body, rating: isNaN(rating) ? null : rating });
                }
                return out;
            }"""
        )
    except Exception as e:
        logger.warning("Review extraction failed: %s", e)

    if not cards:
        logger.warning("No reviews found on %s (page may be blocked or empty)", reviews_url)
        return

    output["reviews"] = [c["text"] for c in cards]
    output["review_ratings"] = [c["rating"] if c["rating"] is not None else "" for c in cards]
    logger.info("Extracted %d reviews", len(cards))


def scrape_product(page, cfg: dict, url: str, output: dict):
    logger.info("Scraping: %s", url)

    name_selector = cfg["name"].split(",")[0].strip()

    for attempt in range(3):  # retry — sites occasionally serve empty shells
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(1.0)

        # Wait for the product title to actually render — an empty body is
        # usually a block/captcha, and it's cheaper to wait once than retry.
        try:
            page.wait_for_selector(name_selector, timeout=12000)
        except Exception:
            pass

        if looks_like_captcha(page, cfg["captcha_markers"]):
            logger.warning("Possible captcha on product page %s", url)

        output["url"] = url
        output["name"] = first_text(page, cfg["name"])
        output["price"] = first_text(page, cfg["price"])
        if not output["price"] and cfg.get("price_pattern"):
            output["price"] = match_price(page, cfg["price_pattern"])
        output["description"] = first_text(page, cfg["description"])
        if output["name"]:
            break
        logger.warning("Empty page for %s (attempt %d) — retrying...", url, attempt + 1)
        time.sleep(3)

    desc = output["description"]
    for junk in ("About this item", "› See more product details", "See more product details"):
        desc = desc.replace(junk, "").strip()
    output["description"] = desc

    if cfg.get("reviews_page"):
        scrape_reviews_page(page, cfg, url, output)
        return

    reviews, ratings = [], []
    try:
        page.mouse.wheel(0, 2500)
        time.sleep(0.8)
        page.mouse.wheel(0, 2500)
        time.sleep(0.8)

        blocks = page.locator(cfg["review_block"]).all()
        for block in blocks[:MAX_REVIEWS_PER_PRODUCT]:
            try:
                text = block.locator(cfg["review_text"]).first.inner_text(timeout=3000).strip()
                if text:
                    reviews.append(text)
            except Exception:
                continue
            try:
                rating = block.locator(cfg["review_rating"]).first.inner_text(timeout=3000).strip()
                ratings.append(rating)
            except Exception:
                ratings.append("")
    except Exception:
        pass

    output["reviews"] = reviews
    output["review_ratings"] = ratings


# ---------------------------------------------------------------------------
# Value conversion helpers
# ---------------------------------------------------------------------------

def to_price(value):
    """'₹223.00' / '₹239' / 224.0 -> 224.0, else None."""
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"[\d,]+(?:\.\d+)?", value or "")
    return float(m.group().replace(",", "")) if m else None


def to_rating(value):
    """'5 out of 5 stars' / '5' / 5.0 -> 5.0, else None."""
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(m.group()) if m else None


def to_product_dict(site: str, row: dict) -> dict:
    """Convert a raw scraped row into the pipeline's product dict shape."""
    ratings = [to_rating(r) for r in row.get("review_ratings", [])]
    numeric = [r for r in ratings if r is not None]
    avg_rating = round(sum(numeric) / len(numeric), 1) if numeric else None

    reviews = []
    for text, rating in zip(row.get("reviews", []), ratings):
        reviews.append({"author": "", "text": text, "star_rating": rating})

    return {
        "name": row.get("name", ""),
        "source_site": site,
        "url": row.get("url", ""),
        "price": to_price(row.get("price", "")),
        "description": row.get("description", ""),
        "image_url": "",
        "rating": avg_rating,
        "reviews": reviews,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _block_heavy_resources(route):
    """Skip images/media/fonts — we only need text, so this loads pages faster."""
    if route.request.resource_type in ("image", "media", "font"):
        route.abort()
    else:
        route.continue_()


def scrape_site(site: str, query: str, max_items: int = DEFAULT_MAX_PER_SITE,
                on_progress=None) -> list[dict]:
    """Scrape one site for a search term, return product dicts for the pipeline.

    on_progress(msg, detail) is an optional callback invoked as scraping
    advances (site started, URLs found, per-product, reviews extracted)."""
    if site not in SITES:
        logger.error("Unknown site '%s'. Choose from: %s", site, ", ".join(SITES))
        return []
    cfg = SITES[site]
    site_label = cfg.get("label", site)

    def report(msg, detail=None):
        if on_progress:
            try:
                on_progress(msg, detail)
            except Exception:
                logger.warning("progress callback failed", exc_info=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not cfg.get("force_headed"),
            args=["--no-sandbox", "--disable-http2"],
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            locale="en-IN",
            viewport={"width": 1366, "height": 768},
        )
        Stealth().apply_stealth_sync(page)
        page.route("**/*", _block_heavy_resources)

        try:
            report(f"Searching {site_label}...")
            urls = discover_urls(page, cfg, query, max_items)
            if not urls:
                report(f"{site_label}: no products found", "done")
            else:
                report(f"{site_label}: {len(urls)} products found, scraping...")
            products = []
            for i, u in enumerate(urls, start=1):
                row = {}
                scrape_product(page, cfg, u, row)
                prod = to_product_dict(site, row)
                if not prod.get("name", "").strip():
                    logger.warning("Dropping %s product with no name (page blocked/empty): %s", site, u)
                    continue
                products.append(prod)
                report(
                    f"{site_label}: scraped {i}/{len(urls)} products "
                    f"({len(prod.get('reviews', []))} reviews)",
                    "progress",
                )
                time.sleep(random_uniform(MIN_DELAY, MAX_DELAY))
        except Exception as e:
            logger.error("Scrape failed for %s: %s", site, e)
            return []
        finally:
            browser.close()

    return products


def random_uniform(a: float, b: float) -> float:
    import random
    return random.uniform(a, b)
