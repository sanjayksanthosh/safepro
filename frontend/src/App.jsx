import React, { useState, useRef, useEffect, useMemo } from "react";
import { searchProducts } from "./api.js";

const SITE_COLORS = {
  Amazon: "#ff9900",
  Flipkart: "#2874f0",
  Myntra: "#ff3f6c",
};

const SORT_OPTIONS = [
  { id: "recommended", label: "Recommended · trust score" },
  { id: "price_asc", label: "Price · low to high" },
  { id: "price_desc", label: "Price · high to low" },
  { id: "rating", label: "Listed rating · high to low" },
  { id: "reviews", label: "Most reviews" },
];

const clean = (s) => String(s || "").replace(/\s+/g, " ").trim();
const shortName = (n) => (n.length > 24 ? n.slice(0, 24) + "…" : n);
const fmt = (n) => "₹" + Number(n).toLocaleString("en-IN");
const refinedStars = (score) => (score ?? 0) / 20;
const flaggedPct = (p) => Math.max(0, Math.round(100 - (p.genuine_review_pct ?? 0)));
const noReviews = (p) => !p.reviews || p.reviews.length === 0;

function verdict(p) {
  if (noReviews(p)) return "unknown";
  return (p.trust_score ?? 0) >= 60 ? "authentic" : "suspect";
}

function medianPrice(list) {
  const prices = list.map((p) => p.price).filter((x) => x != null).sort((a, b) => a - b);
  if (!prices.length) return null;
  return prices[Math.floor(prices.length / 2)];
}

function sentimentSplit(reviews) {
  if (!reviews || !reviews.length) return { positive: 0, neutral: 100, negative: 0 };
  let pos = 0, neu = 0, neg = 0;
  for (const r of reviews) {
    const s = r.sentiment_score ?? 0.5;
    if (s >= 0.6) pos++;
    else if (s <= 0.4) neg++;
    else neu++;
  }
  const n = reviews.length;
  return {
    positive: Math.round((pos / n) * 100),
    neutral: Math.round((neu / n) * 100),
    negative: Math.round((neg / n) * 100),
  };
}

function buildSignals(p, all) {
  const median = medianPrice(all);
  const dev = median && p.price != null ? Math.abs(p.price - median) / median : 0;
  const priceScore = Math.max(0, Math.round(100 - dev * 160));
  const desc = clean(p.description);
  const descScore = desc.length ? Math.min(100, Math.round(55 + desc.length / 25)) : 30;
  return [
    {
      label: "Review authenticity",
      score: noReviews(p) ? 0 : (p.genuine_review_pct ?? 0),
      note: noReviews(p)
        ? "No reviews scraped"
        : `${flaggedPct(p)}% of ${p.reviews.length} reviews flagged as fake`,
    },
    {
      label: "Average sentiment",
      score: noReviews(p) ? 0 : Math.round((p.avg_sentiment ?? 0) * 100),
      note: noReviews(p) ? "No reviews scraped" : "Sentiment across scraped reviews",
    },
    {
      label: "Price consistency",
      score: priceScore,
      note: median
        ? dev === 0
          ? "Matches median price"
          : `${Math.round(dev * 100)}% ${p.price > median ? "above" : "below"} median ${fmt(median)}`
        : "Only one listing",
    },
    {
      label: "Description integrity",
      score: descScore,
      note: desc.length ? "Listing description present" : "No description scraped",
    },
  ];
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
      return arr.sort((a, b) => (b.trust_score ?? 0) - (a.trust_score ?? 0));
  }
}

/* ---------- Icons ---------- */

function Icon({ id, className }) {
  return <svg className={`ico ${className || ""}`}><use href={`#${id}`} /></svg>;
}

function Icons() {
  return (
    <svg style={{ display: "none" }}>
      <symbol id="i-shield" viewBox="0 0 24 24"><path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V6l8-3 8 3z"/><path d="m9 12 2 2 4-4"/></symbol>
      <symbol id="i-alert" viewBox="0 0 24 24"><path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V6l8-3 8 3z"/><path d="M12 8v4"/><path d="M12 16h.01"/></symbol>
      <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></symbol>
      <symbol id="i-arrow" viewBox="0 0 24 24"><path d="M7 17 17 7"/><path d="M8 7h9v9"/></symbol>
      <symbol id="i-trend" viewBox="0 0 24 24"><path d="m3 7 6 6 4-4 8 8"/><path d="M21 17v-5h-5"/></symbol>
      <symbol id="i-flag" viewBox="0 0 24 24"><path d="M4 15V4h12l-2 4 2 4H4"/><path d="M4 21v-6"/></symbol>
      <symbol id="i-check" viewBox="0 0 24 24"><path d="m4 12 5 5L20 6"/></symbol>
      <symbol id="i-spark" viewBox="0 0 24 24"><path d="M12 3v6M12 15v6M3 12h6M15 12h6"/><path d="m6 6 3 3M15 15l3 3M18 6l-3 3M9 15l-3 3"/></symbol>
    </svg>
  );
}

/* ---------- Bits ---------- */

function SiteTag({ site }) {
  return (
    <span className="plat-tag" style={{ "--sc": SITE_COLORS[site] || "#8b8578" }}>
      <i />{site}
    </span>
  );
}

function VerdictPill({ v }) {
  if (v === "authentic")
    return <span className="pill ok"><Icon id="i-shield" /><span>Likely authentic</span></span>;
  if (v === "suspect")
    return <span className="pill bad"><Icon id="i-alert" /><span>Counterfeit risk</span></span>;
  return <span className="pill"><Icon id="i-search" /><span>Insufficient data</span></span>;
}

function TrustRing({ score, v }) {
  const r = 52, c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score ?? 0));
  const stroke =
    v === "authentic" ? "var(--authentic)" : v === "suspect" ? "var(--suspect)" : "#c8c0b4";
  return (
    <div className="ring">
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--sand)" strokeWidth="10" />
        <circle
          cx="60" cy="60" r={r} fill="none" stroke={stroke} strokeWidth="10"
          strokeLinecap="round" strokeDasharray={`${(pct / 100) * c} ${c}`}
        />
      </svg>
      <div className="val">
        <b>{v === "unknown" ? "—" : Math.round(pct)}</b>
        <span className="eyebrow">trust</span>
      </div>
    </div>
  );
}

function Stars({ value }) {
  const full = Math.round(value);
  return (
    <span className="stars" aria-label={`${value.toFixed(1)} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= full ? "on" : ""}>★</span>
      ))}
    </span>
  );
}

function Signal({ s }) {
  return (
    <div className="signal">
      <div className="row">
        <span>{s.label}</span>
        <span>{s.score}</span>
      </div>
      <div className="bar">
        <i style={{ width: `${s.score}%`, background: s.score >= 60 ? "var(--authentic)" : "var(--suspect)" }} />
      </div>
      <p>{s.note}</p>
    </div>
  );
}

/* ---------- Header ---------- */

function SiteHeader() {
  return (
    <header>
      <div className="wrap navrow">
        <div className="brand">
          <span className="mark"><Icon id="i-shield" /></span>
          <span>Safe-pro</span>
        </div>
        <nav>
          <a href="#analysis">Analysis</a>
          <a href="#compare">Compare</a>
          <a href="#pipeline">How it works</a>
        </nav>
        <a className="btn" href="#search">Scan a product</a>
      </div>
    </header>
  );
}

/* ---------- Hero ---------- */

function Hero({ onSearch, loading }) {
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
    <section className="wrap hero" id="search">
      <span className="eyebrow">Product authentication · beauty</span>
      <h1>Know what&rsquo;s real <em>before</em> you buy it.</h1>
      <p className="lede">
        Safe-pro scrapes listings, prices and reviews across Amazon, Flipkart and
        Myntra, filters out fake reviews, and shows you a refined score you can
        actually trust.
      </p>
      <form className="searchbar" onSubmit={submit}>
        <Icon id="i-search" />
        <input
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Search a beauty product — sunscreen, serum, lipstick…"
          aria-label="Search a beauty product"
          disabled={loading}
        />
        <button className="btn" disabled={loading}>
          {loading ? "Scanning…" : "Verify"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      <dl className="stats">
        <div><dt>3</dt><dd>Marketplaces scraped</dd></div>
        <div><dt>AI</dt><dd>Fake-review detection</dd></div>
        <div><dt>24h</dt><dd>Results cached</dd></div>
      </dl>
    </section>
  );
}

/* ---------- Processing ---------- */

function ProcessingView({ term, progress }) {
  return (
    <section className="wrap">
      <div className="card pad processing-card">
        <div className="spinner" />
        <h2>Scanning &ldquo;{term}&rdquo;</h2>
        <p className="muted" style={{ maxWidth: "32rem", margin: "0 auto" }}>
          Live-scraping Amazon, Flipkart and Myntra, then running review-authenticity
          analysis. This usually takes a few minutes.
        </p>
        {progress && <p className="progress-msg mono">{progress}</p>}
        <div className="progress-track"><div className="progress-bar" /></div>
      </div>
    </section>
  );
}

/* ---------- Analysis ---------- */

function AnalysisPanel({ product, all }) {
  const v = verdict(product);
  const sents = sentimentSplit(product.reviews);
  const signals = buildSignals(product, all);
  const desc = clean(product.description);
  return (
    <div className="analysis">
      <div className="card pad">
        <div className="prodhead">
          <div>
            <p className="eyebrow"><SiteTag site={product.source_site} /></p>
            <h3>{product.name}</h3>
            <div className="prod-meta">
              {product.price != null && <span className="price">{fmt(product.price)}</span>}
              {product.rating != null && (
                <span className="rating-chip"><span>★</span>{product.rating.toFixed(1)}</span>
              )}
              <span className="muted" style={{ fontSize: ".75rem" }}>
                {product.reviews?.length ?? 0} reviews analysed
              </span>
            </div>
            <div className="prod-actions">
              <VerdictPill v={v} />
              {product.url && (
                <a className="btn btn-sm" href={product.url} target="_blank" rel="noreferrer">
                  Open on {product.source_site} <Icon id="i-arrow" />
                </a>
              )}
            </div>
          </div>
          <div className="prodhead-right">
            <TrustRing score={product.trust_score} v={v} />
            <span className="refined-stars">
              <Stars value={noReviews(product) ? 0 : refinedStars(product.trust_score)} />
              <span className="eyebrow">
                {noReviews(product)
                  ? "no review data"
                  : `${refinedStars(product.trust_score).toFixed(1)} refined rating`}
              </span>
            </span>
          </div>
        </div>
        {desc && <p className="summary">{desc}</p>}
        {signals.map((s, i) => <Signal key={i} s={s} />)}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="card pad">
          <span className="eyebrow">Review sentiment</span>
          <div className="senti">
            <div style={{ width: `${sents.positive}%`, background: "var(--authentic)" }} />
            <div style={{ width: `${sents.neutral}%`, background: "var(--sand)" }} />
            <div style={{ width: `${sents.negative}%`, background: "var(--suspect)" }} />
          </div>
          <div className="senti-legend">
            <span>{sents.positive}% positive</span>
            <span>{sents.neutral}% neutral</span>
            <span>{sents.negative}% negative</span>
          </div>
          {noReviews(product) ? (
            <p className="muted" style={{ marginTop: "1rem", fontSize: ".875rem" }}>
              No review data was scraped for this product — the site may have blocked
              the review section.
            </p>
          ) : (
            product.reviews.map((r, i) => {
              const fake = r.fake_probability >= 0.5;
              return (
                <div key={i} className={`review ${fake ? "flag" : ""}`}>
                  <div className="top">
                    <span>{r.author || "Anonymous"}</span>
                    <b className={fake ? "bad-t" : "ok-t"}>
                      <Icon id={fake ? "i-flag" : "i-check"} />
                      {fake
                        ? `${Math.round(r.fake_probability * 100)}% likely fake`
                        : `${Math.round((1 - r.fake_probability) * 100)}% genuine`}
                    </b>
                  </div>
                  <q>{r.text}</q>
                  <p>
                    Sentiment {Math.round((r.sentiment_score ?? 0.5) * 100)}%
                    {r.star_rating != null ? ` · ★ ${r.star_rating}` : ""}
                  </p>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

function AnalysisSection({ products, selected, onSelect }) {
  return (
    <section className="band warm" id="analysis">
      <div className="wrap">
        <div className="sechead">
          <div>
            <span className="eyebrow">Live analysis</span>
            <h2>One verdict, three marketplaces.</h2>
          </div>
          <div className="tabs" role="tablist">
            {products.map((p) => (
              <button
                key={p.id}
                role="tab"
                aria-selected={selected.id === p.id}
                className="tab"
                onClick={() => onSelect(p.id)}
              >
                {shortName(p.name)}
              </button>
            ))}
          </div>
        </div>
        <AnalysisPanel product={selected} all={products} />
      </div>
    </section>
  );
}

/* ---------- Compare ---------- */

function CompareSection({ products, sort, onSort }) {
  const sorted = sortProducts(products, sort);
  const best = [...products].sort((a, b) => (b.trust_score ?? 0) - (a.trust_score ?? 0))[0];
  const cheapest = [...products].filter((p) => p.price != null).sort((a, b) => a.price - b.price)[0];
  return (
    <section className="wrap plain" id="compare">
      <div className="sechead">
        <div>
          <span className="eyebrow">Refined ratings</span>
          <h2 style={{ maxWidth: "42rem" }}>
            The star rating you see isn&rsquo;t the rating you should trust.
          </h2>
        </div>
        <label className="sort-control">
          <span className="eyebrow">Sort by</span>
          <select value={sort} onChange={(e) => onSort(e.target.value)}>
            {SORT_OPTIONS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </label>
      </div>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th className="eyebrow">Product</th>
              <th className="eyebrow">Listed rating</th>
              <th className="eyebrow">Refined rating</th>
              <th className="eyebrow">Flagged reviews</th>
              <th className="eyebrow">Price</th>
              <th className="eyebrow">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const v = verdict(p);
              const isBest = best && best.id === p.id;
              return (
                <tr key={p.id} className={isBest ? "row-best" : ""}>
                  <td>
                    {p.url ? (
                      <a
                        className="prod-link"
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        title={`Open on ${p.source_site}`}
                      >
                        {p.name} <Icon id="i-arrow" />
                      </a>
                    ) : (
                      <strong>{p.name}</strong>
                    )}
                    <small>
                      <SiteTag site={p.source_site} />
                      <span className="review-count">· {p.reviews?.length ?? 0} reviews</span>
                    </small>
                  </td>
                  <td className="mono muted strike">
                    {p.rating != null ? p.rating.toFixed(1) : "—"}
                  </td>
                  <td className="mono" style={{ fontWeight: 500 }}>
                    {noReviews(p) ? "—" : refinedStars(p.trust_score).toFixed(1)}
                  </td>
                  <td className="mono">{noReviews(p) ? "—" : `${flaggedPct(p)}%`}</td>
                  <td className="mono">{p.price != null ? fmt(p.price) : "—"}</td>
                  <td><VerdictPill v={v} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="listfoot warm">
        <span>
          Cheapest listing{" "}
          {cheapest
            ? `${fmt(cheapest.price)} on ${cheapest.source_site}${verdict(cheapest) === "suspect" ? " — flagged" : ""}`
            : "—"}
        </span>
        <span>
          Best overall trust:{" "}
          <b>{best ? `${best.source_site} · ${Math.round(best.trust_score)}/100` : ""}</b>
        </span>
      </div>
    </section>
  );
}

/* ---------- Pipeline / CTA / Footer ---------- */

function Pipeline() {
  return (
    <section className="plain" id="pipeline" style={{ borderTop: "1px solid var(--border)", background: "var(--card)" }}>
      <div className="wrap">
        <span className="eyebrow">The pipeline</span>
        <h2 style={{ maxWidth: "34rem" }}>From raw listing to a decision you can act on.</h2>
        <div className="steps">
          <div className="step"><span>01</span><h3>Collect</h3><p>Listings, prices and reviews scraped across Amazon, Flipkart and Myntra.</p></div>
          <div className="step"><span>02</span><h3>Clean</h3><p>Noise, emoji and boilerplate stripped from review text.</p></div>
          <div className="step"><span>03</span><h3>Analyse</h3><p>NLP reads sentiment, claims and suspicious phrasing.</p></div>
          <div className="step"><span>04</span><h3>Classify</h3><p>An ML model scores each review and listing for authenticity.</p></div>
        </div>
        <div className="feats">
          <div className="card lift feat"><Icon id="i-spark" className="feat-ico" /><h3>Sentiment that counts</h3><p>Only reviews that survive the fake filter feed the score.</p></div>
          <div className="card lift feat"><Icon id="i-trend" className="feat-ico" /><h3>Price anomaly watch</h3><p>Listings priced far below the median get flagged, not celebrated.</p></div>
          <div className="card lift feat"><Icon id="i-shield" className="feat-ico" /><h3>One trustworthy tab</h3><p>No hopping between marketplaces to compare what&rsquo;s real.</p></div>
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="wrap plain">
      <div className="card warm cta">
        <h2 style={{ maxWidth: "36rem" }}>Shop on transparency, not manipulation.</h2>
        <p className="muted" style={{ maxWidth: "34rem", fontSize: ".875rem" }}>
          Safe-Pro turns scattered listings, noisy reviews and shifting prices into
          one honest verdict — before the product reaches your skin.
        </p>
        <a className="btn" href="#search" style={{ padding: ".75rem 1.5rem" }}>Try a scan</a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer>
      <div className="wrap footrow">
        <span>Safe-Pro — intelligent product comparison &amp; review authentication</span>
        <span className="mono">Live scrapes from Amazon, Flipkart &amp; Myntra</span>
      </div>
    </footer>
  );
}

/* ---------- App ---------- */

function App() {
  const [term, setTerm] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [sort, setSort] = useState("recommended");
  const [selectedId, setSelectedId] = useState(null);
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
                const list = cleanResults(d.results);
                setResults(list);
                if (list.length) setSelectedId(list[0].id);
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
        const list = cleanResults(data.results);
        setResults(list);
        if (list.length) setSelectedId(list[0].id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const cleanResults = (list) => (list || []).filter((p) => p.name && String(p.name).trim());

  const selected = useMemo(
    () => results?.find((p) => p.id === selectedId) || results?.[0] || null,
    [results, selectedId]
  );

  return (
    <div className="app">
      <Icons />
      <SiteHeader />
      <main>
        <Hero onSearch={handleSearch} loading={loading || processing} />

        {error && <p className="error banner wrap">{error}</p>}
        {processing && <ProcessingView term={term} progress={progress} />}

        {!processing && results && results.length > 0 && selected && (
          <>
            <AnalysisSection products={results} selected={selected} onSelect={setSelectedId} />
            <CompareSection products={results} sort={sort} onSort={setSort} />
          </>
        )}

        {!processing && results && results.length === 0 && (
          <p className="empty wrap card pad">
            No products found for &ldquo;{term}&rdquo;. Try a different search term.
          </p>
        )}

        <Pipeline />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}

export default App;
