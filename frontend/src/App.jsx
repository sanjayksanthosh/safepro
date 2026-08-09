import React, { useState, useRef, useEffect } from "react";
import { searchProducts, getProduct } from "./api.js";

const SITE_COLORS = {
  Amazon: "#ff9900",
  Flipkart: "#2874f0",
  Myntra: "#ff3f6c",
};

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
      <input
        type="text"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder="e.g. face serum, sunscreen, lipstick..."
        disabled={loading}
      />
      <button type="submit" disabled={loading}>
        {loading ? "Searching..." : "Search"}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function TrustRing({ score, noData }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const pct = noData ? 0 : Math.max(0, Math.min(100, score));
  const color = noData ? "#9ca3af" : pct >= 75 ? "#16a34a" : pct >= 50 ? "#d97706" : "#dc2626";
  return (
    <svg viewBox="0 0 80 80" className="trust-ring">
      <circle cx="40" cy="40" r={r} className="ring-bg" />
      <circle
        cx="40"
        cy="40"
        r={r}
        className="ring-fg"
        stroke={color}
        strokeDasharray={`${(pct / 100) * c} ${c}`}
        transform="rotate(-90 40 40)"
      />
      <text x="40" y="44" textAnchor="middle" className="ring-text">
        {noData ? "—" : Math.round(pct)}
      </text>
    </svg>
  );
}

function ProductCard({ product, onSelect, highlight }) {
  const noReviews = !product.reviews || product.reviews.length === 0;
  return (
    <button
      className={`product-card ${highlight ? "highlight" : ""}`}
      onClick={() => onSelect(product.id)}
    >
      {highlight && <span className="badge">Best Product</span>}
      <TrustRing score={product.trust_score} noData={noReviews} />
      <div className="product-info">
        <h3>{product.name}</h3>
        <p className="meta">
          <span
            className="site-tag"
            style={{ backgroundColor: SITE_COLORS[product.source_site] }}
          >
            {product.source_site}
          </span>
          {product.price != null && (
            <span className="price">Rs. {Number(product.price).toLocaleString()}</span>
          )}
          {product.rating != null && (
            <span className="rating">&#9733; {product.rating}</span>
          )}
        </p>
        <p className="sub-meta">
          {noReviews ? (
            "No review data scraped"
          ) : (
            <>
              Trust {Math.round(product.trust_score)}% &middot; Sentiment{" "}
              {Math.round(product.avg_sentiment * 100)}% &middot;{" "}
              {product.genuine_review_pct}% genuine reviews
            </>
          )}
        </p>
      </div>
    </button>
  );
}

function ReviewRow({ review }) {
  const fake = review.fake_probability >= 0.5;
  return (
    <li className={`review ${fake ? "fake" : ""}`}>
      <p className="review-text">{review.text}</p>
      <p className="review-meta">
        {review.author && <span>{review.author} &middot; </span>}
        {review.star_rating != null && <span>&#9733; {review.star_rating} &middot; </span>}
        <span>
          Sentiment {Math.round(review.sentiment_score * 100)}% &middot;{" "}
          {fake ? "Likely fake" : "Likely genuine"}
        </span>
      </p>
    </li>
  );
}

function ProductDetail({ product, onBack }) {
  const noReviews = !product.reviews || product.reviews.length === 0;
  return (
    <div className="detail">
      <button className="back" onClick={onBack}>
        &larr; Back to results
      </button>
      <div className="detail-head">
        <TrustRing score={product.trust_score} noData={noReviews} />
        <div>
          <h2>{product.name}</h2>
          <p className="meta">
            <span
              className="site-tag"
              style={{ backgroundColor: SITE_COLORS[product.source_site] }}
            >
              {product.source_site}
            </span>
            {product.price != null && (
              <span className="price">Rs. {Number(product.price).toLocaleString()}</span>
            )}
            {product.rating != null && <span className="rating">&#9733; {product.rating}</span>}
          </p>
          <a href={product.url} target="_blank" rel="noreferrer">
            View on {product.source_site}
          </a>
        </div>
      </div>
      {product.description && <p className="description">{product.description}</p>}
      <h3>Reviews ({product.reviews.length})</h3>
      {noReviews ? (
        <p className="empty">
          No review data was scraped for this product (the site may have blocked
          the review section).
        </p>
      ) : (
        <ul className="review-list">
          {product.reviews.map((r, i) => (
            <ReviewRow key={i} review={r} />
          ))}
        </ul>
      )}
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
              setResults(cleanResults(d.results));
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

  const best = results && results.length ? results[0] : null;

  return (
    <div className="app">
      <header>
        <h1>Safe-Pro</h1>
        <p className="tagline">
          Trusted beauty product comparison with fake-review detection
        </p>
      </header>
      <SearchBar onSearch={handleSearch} loading={loading || processing} />

      {error && <p className="error banner">{error}</p>}

      {processing && (
        <div className="processing">
          <div className="spinner" />
          <p>
            Searching <strong>{term}</strong> across Amazon, Flipkart and Myntra...
          </p>
          {progress && <p className="progress-msg">{progress}</p>}
          <p className="progress-hint">
            Live scraping takes a few minutes; results appear automatically when done.
          </p>
        </div>
      )}

      {!processing && results && !selected && (
        <section>
          <h2>
            {results.length} products compared{term ? ` for "${term}"` : ""}
          </h2>
          {results.length === 0 && (
            <p className="empty">No products found. Try a different search term.</p>
          )}
          <div className="product-list">
            {results.map((p, i) => (
              <ProductCard
                key={p.id}
                product={p}
                onSelect={openProduct}
                highlight={best && best.id === p.id}
              />
            ))}
          </div>
        </section>
      )}

      {selected && <ProductDetail product={selected} onBack={() => setSelected(null)} />}
    </div>
  );
}

export default App;
