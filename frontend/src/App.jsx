import React, { useState, useRef, useEffect, useMemo } from "react";
import { searchProducts, getProduct } from "./api.js";

const SITES = {
  Amazon: { color: "#ff9900", short: "AZ" },
  Flipkart: { color: "#2874f0", short: "FK" },
  Myntra: { color: "#ff3f6c", short: "MN" },
};

const SORT_OPTIONS = [
  { id: "recommended", label: "Recommended (trust score)" },
  { id: "price_asc", label: "Price: Low to High" },
  { id: "price_desc", label: "Price: High to Low" },
  { id: "rating", label: "Rating: High to Low" },
  { id: "reviews", label: "Most reviews" },
];

function cleanText(s) {
  if (!s) return "";
  return String(s).replace(/\s+/g, " ").trim();
}

function sortProducts(list, sort) {
  const arr = [...list];
  switch (sort) {
    case "price_asc":
      return arr.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
    case "price_desc":
      return arr.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity));
    case "rating":
      return arr.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
    case "reviews":
      return arr.sort((a, b) => (b.reviews?.length ?? 0) - (a.reviews?.length ?? 0));
    default:
      return arr.sort(
        (a, b) =>
          (b.trust_score ?? 0) - (a.trust_score ?? 0) ||
          (b.genuine_review_pct ?? 0) - (a.genuine_review_pct ?? 0)
      );
  }
}

function ringColor(score, noData) {
  if (noData) return "#9ca3af";
  if (score >= 75) return "#16a34a";
  if (score >= 50) return "#d97706";
  return "#dc2626";
}

function TrustRing({ score, noData, size = 76 }) {
  const r = size / 2 - 7;
  const c = 2 * Math.PI * r;
  const pct = noData ? 0 : Math.max(0, Math.min(100, score));
  const color = ringColor(score, noData);
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="trust-ring"
      style={{ width: size, height: size }}
    >
      <circle cx={size / 2} cy={size / 2} r={r} className="ring-bg" strokeWidth={7} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        className="ring-fg"
        stroke={color}
        strokeDasharray={`${(pct / 100) * c} ${c}`}
        strokeWidth={7}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="55%" textAnchor="middle" dominantBaseline="middle" className="ring-text">
        {noData ? "—" : Math.round(pct)}
      </text>
    </svg>
  );
}

function SiteBadge({ site }) {
  const info = SITES[site] || { color: "#6b7280", short: "?" };
  return (
    <span
      className="site-badge"
      style={{ backgroundColor: info.color }}
      title={`Sold on ${site}`}
    >
      <span className="site-dot" style={{ backgroundColor: "#ffffff" }} />
      {site}
    </span>
  );
}

function SearchBar({ onSearch, loading }) {
  const [term, setTerm] = useState("");
  const [error, setError] = useState("");
  const submit = (e) => {
    e.preventDefault();
    const q = term.trim();
    if (!q) {
      setError("Enter a product name to search");
      return;
    }
    setError("");
    onSearch(q);
  };
  return (
    <form className="search-bar" onSubmit={submit}>
      <div className="search-field">
        <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="text"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Try sunscreen, face serum, lipstick, face wash…"
          disabled={loading}
        />
      </div>
      <button type="submit" className="btn-primary" disabled={loading}>
        {loading ? (
          <>
            <span className="spinner-sm" /> Searching…
          </>
        ) : (
          "Search"
        )}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function ProcessingView({ term, progress }) {
  return (
    <div className="processing card">
      <div className="spinner" />
      <h3>Searching <span className="accent">{term}</span></h3>
      <p className="muted">
        We&apos;re live-scraping Amazon, Flipkart and Myntra and running our
        fake-review detection. This usually takes a few minutes.
      </p>
      {progress && <p className="progress-msg">{progress}</p>}
      <div className="progress-track">
        <div className="progress-bar" />
      </div>
    </div>
  );
}

function ProductCard({ product, onSelect, isBest, rank }) {
  const noReviews = !product.reviews || product.reviews.length === 0;
  const info = SITES[product.source_site] || { color: "#6b7280", short: "?" };
  const desc = cleanText(product.description);
  return (
    <button
      className={`product-card ${isBest ? "best" : ""}`}
      onClick={() => onSelect(product.id)}
    >
      {isBest && (
        <span className="best-ribbon">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
            <path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 14.6l-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z" />
          </svg>
          Best pick
        </span>
      )}
      <div className="card-media" style={{ background: `linear-gradient(135deg, ${info.color}33, ${info.color}18)` }}>
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} loading="lazy" />
        ) : (
          <span className="media-mono">{info.short}</span>
        )}
        {rank !== null && <span className="rank">{rank}</span>}
      </div>
      <div className="card-body">
        <div className="card-top">
          <SiteBadge site={product.source_site} />
          <span className="trust-chip" style={{ color: ringColor(product.trust_score, noReviews) }}>
            Trust {noReviews ? "—" : Math.round(product.trust_score)}%
          </span>
        </div>
        <h3 className="card-title">{product.name}</h3>
        {desc && <p className="card-desc">{desc.slice(0, 110)}{desc.length > 110 ? "…" : ""}</p>}
        <div className="card-meta">
          {product.price != null && <span className="price">₹{Number(product.price).toLocaleString("en-IN")}</span>}
          {product.rating != null && (
            <span className="rating-chip">★ {product.rating}</span>
          )}
          {!noReviews && (
            <span className="muted">{product.reviews.length} reviews</span>
          )}
        </div>
      </div>
      <div className="card-score">
        <TrustRing score={product.trust_score} noData={noReviews} />
        <span className="score-label">trust score</span>
      </div>
    </button>
  );
}

function ResultsToolbar({ count, term, sort, onSort }) {
  return (
    <div className="toolbar">
      <p className="results-title">
        <strong>{count}</strong> {count === 1 ? "product" : "products"} compared
        {term ? ` for “${term}”` : ""}
      </p>
      <label className="sort-control">
        <span>Sort by</span>
        <select value={sort} onChange={(e) => onSort(e.target.value)}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function StatPill({ label, value, color }) {
  return (
    <div className="stat-pill">
      <span className="stat-value" style={{ color }}>
        {value}
      </span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function ProductDetail({ product, onBack }) {
  const noReviews = !product.reviews || product.reviews.length === 0;
  const info = SITES[product.source_site] || { color: "#6b7280", short: "?" };
  const desc = cleanText(product.description);
  const genuineCount = product.reviews?.filter((r) => r.fake_probability < 0.5).length ?? 0;

  return (
    <div className="detail card">
      <button className="back" onClick={onBack}>
        ← Back to results
      </button>

      <div className="detail-head">
        <div
          className="detail-media"
          style={{ background: `linear-gradient(135deg, ${info.color}33, ${info.color}18)` }}
        >
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} />
          ) : (
            <span className="media-mono">{info.short}</span>
          )}
        </div>
        <div className="detail-main">
          <SiteBadge site={product.source_site} />
          <h2>{product.name}</h2>
          <div className="detail-meta">
            {product.price != null && (
              <span className="price big">₹{Number(product.price).toLocaleString("en-IN")}</span>
            )}
            {product.rating != null && <span className="rating-chip big">★ {product.rating}</span>}
          </div>
          <a href={product.url} target="_blank" rel="noreferrer" className="btn-outline">
            View on {product.source_site} ↗
          </a>
        </div>
        <div className="detail-score">
          <TrustRing score={product.trust_score} noData={noReviews} size={96} />
          <span className="score-label">overall trust</span>
        </div>
      </div>

      <div className="stats-row">
        <StatPill
          label="Trust score"
          value={noReviews ? "—" : `${Math.round(product.trust_score)}%`}
          color={ringColor(product.trust_score, noReviews)}
        />
        <StatPill
          label="Avg sentiment"
          value={noReviews ? "—" : `${Math.round((product.avg_sentiment ?? 0) * 100)}%`}
          color="#2563eb"
        />
        <StatPill
          label="Genuine reviews"
          value={noReviews ? "—" : `${product.genuine_review_pct ?? 0}%`}
          color="#16a34a"
        />
        <StatPill
          label="Reviews checked"
          value={product.reviews?.length ?? 0}
          color="#6b7280"
        />
      </div>

      {desc && (
        <section className="detail-section">
          <h3>About this product</h3>
          <p className="description">{desc}</p>
        </section>
      )}

      <section className="detail-section">
        <h3>
          Review analysis
          {!noReviews && (
            <span className="review-summary">
              {genuineCount} genuine · {product.reviews.length - genuineCount} flagged as fake
            </span>
          )}
        </h3>
        {noReviews ? (
          <p className="empty">
            No review data was scraped for this product (the site may have blocked
            the review section).
          </p>
        ) : (
          <ul className="review-list">
            {product.reviews.map((r, i) => {
              const fake = r.fake_probability >= 0.5;
              return (
                <li key={i} className={`review ${fake ? "fake" : ""}`}>
                  <p className="review-text">{r.text}</p>
                  <p className="review-meta">
                    {r.author && <span className="review-author">{r.author}</span>}
                    {r.star_rating != null && <span>★ {r.star_rating}</span>}
                    <span
                      className={`verdict ${fake ? "fake" : "genuine"}`}
                    >
                      {fake
                        ? `⚠ ${Math.round(r.fake_probability * 100)}% likely fake`
                        : `✓ ${Math.round((1 - r.fake_probability) * 100)}% genuine`}
                    </span>
                    <span>Sentiment {Math.round(r.sentiment_score * 100)}%</span>
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function App() {
  const [term, setTerm] = useState("");
  const [results, setResults] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [sort, setSort] = useState("recommended");
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const handleSearch = async (q) => {
    setError("");
    setSelected(null);
    setProcessing(false);
    setProgress("");
    stopPolling();
    setSort("recommended");
    try {
      setLoading(true);
      const data = await searchProducts(q);
      if (data.processing) {
        setTerm(q);
        setResults(null);
        setProcessing(true);
        setProgress(data.progress || "");
        pollRef.current = setInterval(async () => {
          try {
            const d = await searchProducts(q);
            if (d.progress) setProgress(d.progress);
            if (!d.processing) {
              stopPolling();
              setProcessing(false);
              if (d.error) {
                setError(d.error);
              } else {
                setResults(cleanResults(d.results));
              }
            }
          } catch (err) {
            stopPolling();
            setProcessing(false);
            setError(err.message);
          }
        }, 3000);
      } else if (data.error) {
        setError(data.error);
      } else {
        setResults(cleanResults(data.results));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openProduct = async (id) => {
    try {
      setSelected(await getProduct(id));
    } catch (err) {
      setError(err.message);
    }
  };

  const cleanResults = (list) =>
    (list || []).filter((p) => p.name && String(p.name).trim());

  const sorted = useMemo(() => sortProducts(results || [], sort), [results, sort]);
  const best = useMemo(
    () =>
      results && results.length
        ? [...results].sort(
            (a, b) =>
              (b.trust_score ?? 0) - (a.trust_score ?? 0) ||
              (b.genuine_review_pct ?? 0) - (a.genuine_review_pct ?? 0)
          )[0]
        : null,
    [results]
  );

  return (
    <div className="app">
      <header className="site-header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2 4 7v5c0 5.2 3.4 9.6 8 10.9 4.6-1.3 8-5.7 8-10.9V7z" />
              </svg>
            </span>
            <div>
              <h1>Safe-Pro</h1>
              <p className="tagline">Compare beauty products · detect fake reviews</p>
            </div>
          </div>
          <div className="trust-strip">
            <span>✓ 3 stores</span>
            <span>✓ AI review analysis</span>
            <span>✓ Unbiased scores</span>
          </div>
        </div>
      </header>

      <main>
        <div className="hero">
          <h2>Shop smart, not gullible</h2>
          <p className="hero-sub">
            Search a product and we compare it across Amazon, Flipkart and Myntra —
            then score every review for authenticity so you can trust what you buy.
          </p>
          <SearchBar onSearch={handleSearch} loading={loading || processing} />
        </div>

        {error && <p className="error banner">{error}</p>}

        {processing && <ProcessingView term={term} progress={progress} />}

        {!processing && results && !selected && (
          <section className="results">
            <ResultsToolbar
              count={results.length}
              term={term}
              sort={sort}
              onSort={setSort}
            />
            {results.length === 0 ? (
              <p className="empty card">
                No products found for “{term}”. Try a different search term.
              </p>
            ) : (
              <div className="product-list">
                {sorted.map((p, i) => (
                  <ProductCard
                    key={p.id}
                    product={p}
                    onSelect={openProduct}
                    isBest={best && best.id === p.id}
                    rank={i + 1}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {selected && (
          <ProductDetail
            product={selected}
            onBack={() => setSelected(null)}
          />
        )}
      </main>

      <footer className="site-footer">
        <p>
          Safe-Pro is an independent comparison tool. Prices and availability are
          scraped from public store pages and may change.
        </p>
      </footer>
    </div>
  );
}

export default App;
