export async function searchProducts(term) {
  const res = await fetch(`/api/search?q=${encodeURIComponent(term)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || "Search failed");
  }
  return res.json();
}

export async function getProduct(id) {
  const res = await fetch(`/api/products/${id}/`);
  if (!res.ok) throw new Error("Failed to load product");
  return res.json();
}
