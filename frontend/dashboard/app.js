// CBIR Engine dashboard — build-free vanilla JS talking to the public REST API.
// The dashboard is "just another API consumer" (dogfoods the same endpoints as
// the SDK and external customers), per the architecture's frontend design.

const state = {
  apiKey: localStorage.getItem("cbir_apiKey") || "",
  catalogUrl: localStorage.getItem("cbir_catalogUrl") || "http://localhost:8002",
  queryUrl: localStorage.getItem("cbir_queryUrl") || "http://localhost:8004",
};

const $ = (id) => document.getElementById(id);

function initConn() {
  $("apiKey").value = state.apiKey;
  $("catalogUrl").value = state.catalogUrl;
  $("queryUrl").value = state.queryUrl;
}

function headers() {
  return { "X-API-Key": state.apiKey };
}

function setStatus(el, msg, ok) {
  el.textContent = msg;
  el.className = "status " + (ok ? "ok" : "err");
}

async function api(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.status === 204 ? null : res.json();
}

// --- connect -----------------------------------------------------------------

$("saveConn").onclick = async () => {
  state.apiKey = $("apiKey").value.trim();
  state.catalogUrl = $("catalogUrl").value.trim().replace(/\/$/, "");
  state.queryUrl = $("queryUrl").value.trim().replace(/\/$/, "");
  localStorage.setItem("cbir_apiKey", state.apiKey);
  localStorage.setItem("cbir_catalogUrl", state.catalogUrl);
  localStorage.setItem("cbir_queryUrl", state.queryUrl);
  try {
    await api(`${state.catalogUrl}/v1/items?limit=1`, { headers: headers() });
    setStatus($("connStatus"), "connected ✓", true);
    refreshCatalog();
  } catch (e) {
    setStatus($("connStatus"), e.message, false);
  }
};

// --- catalog -----------------------------------------------------------------

async function refreshCatalog() {
  try {
    const items = await api(`${state.catalogUrl}/v1/items?limit=50`, { headers: headers() });
    $("catalogList").innerHTML = items
      .map(
        (it) =>
          `<div class="item"><span class="id">${it.id.slice(0, 8)}…</span>` +
          `<span>${JSON.stringify(it.metadata)}</span>` +
          `<span class="badge ${it.status}">${it.status}</span></div>`
      )
      .join("");
  } catch (e) {
    $("catalogList").innerHTML = `<div class="item">${e.message}</div>`;
  }
}
$("refreshBtn").onclick = refreshCatalog;

$("uploadBtn").onclick = async () => {
  const file = $("uploadFile").files[0];
  if (!file) return;
  let metadata = {};
  try {
    metadata = $("uploadMeta").value ? JSON.parse($("uploadMeta").value) : {};
  } catch (_) {
    return alert("metadata must be valid JSON");
  }
  try {
    // register -> signed PUT -> confirm
    const reg = await api(`${state.catalogUrl}/v1/items`, {
      method: "POST",
      headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ content_type: file.type || "image/jpeg", metadata }),
    });
    const up = reg.upload;
    const put = await fetch(up.url, { method: up.method, headers: up.headers, body: file });
    if (!put.ok) throw new Error("object upload failed");
    await api(`${state.catalogUrl}/v1/items/${reg.item.id}/confirm`, {
      method: "POST",
      headers: headers(),
    });
    refreshCatalog();
  } catch (e) {
    alert(e.message);
  }
};

// --- search ------------------------------------------------------------------

// Escape untrusted text (tenant-supplied metadata) before putting it in HTML.
function esc(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

// A search result already includes the item_id; we fetch the image's signed
// download URL from the EXISTING catalog endpoint (no backend change) and use
// it as the thumbnail's src. Image <img> loads are not CORS-gated, so the
// browser can display the MinIO/S3 signed URL directly.
async function fetchThumbnail(itemId) {
  try {
    const data = await api(`${state.catalogUrl}/v1/items/${itemId}`, { headers: headers() });
    return data.download_url;
  } catch (_) {
    return null;
  }
}

// The result score is the COSINE SIMILARITY returned by the vector search
// (Qdrant collections use the Cosine metric): higher = more similar, in the
// range -1..1. It is NOT a distance and NOT a confidence percentage, so we
// label it clearly and explain it on hover.
const SIMILARITY_TOOLTIP =
  "Cosine similarity between your query and this image (range -1 to 1; " +
  "higher means more similar). This is the raw vector-search score — " +
  "not a confidence percentage.";

function renderResults(payload) {
  const cached = payload.cached ? " · cached" : "";
  const reranked = payload.reranked ? " · reranked" : "";
  const results = payload.results;
  // Best match is first (results are returned ranked). Used only for a
  // RELATIVE similarity bar — it does not change ranking or the shown score.
  const topScore = results.length ? results[0].score : 1;

  $("results").innerHTML =
    `<div class="results-header">` +
    `<span class="hint">${payload.count} result${payload.count === 1 ? "" : "s"}${cached}${reranked}</span>` +
    `<span class="metric-note" title="${SIMILARITY_TOOLTIP}">ranked by cosine similarity ⓘ</span>` +
    `</div>` +
    `<div class="results-grid">` +
    results
      .map((r, i) => {
        const category =
          r.metadata && r.metadata.category ? esc(r.metadata.category) : "uncategorized";
        const similarity = r.score.toFixed(3);
        const relative = topScore > 0 ? Math.max(0, Math.min(100, (r.score / topScore) * 100)) : 0;
        return (
          `<div class="result-card">` +
          `<div class="thumb-wrap">` +
          `<img class="thumb" id="thumb-${esc(r.item_id)}" alt="${category}" />` +
          `<span class="rank-badge">#${i + 1}</span>` +
          `<span class="cat-badge" title="category: ${category}">${category}</span>` +
          `</div>` +
          `<div class="result-meta">` +
          `<div class="metric" title="${SIMILARITY_TOOLTIP}">` +
          `<span class="metric-label">Similarity</span>` +
          `<span class="metric-value">${similarity}</span>` +
          `</div>` +
          `<div class="sim-bar" title="similarity relative to the top match">` +
          `<span style="width:${relative.toFixed(1)}%"></span></div>` +
          `<span class="id" title="item ${esc(r.item_id)}">${esc(r.item_id.slice(0, 8))}…</span>` +
          `</div>` +
          `</div>`
        );
      })
      .join("") +
    `</div>`;

  // Load each thumbnail from the existing signed-URL endpoint.
  for (const r of payload.results) {
    fetchThumbnail(r.item_id).then((url) => {
      const img = document.getElementById(`thumb-${r.item_id}`);
      if (!img) return;
      if (url) img.src = url;
      else img.closest(".thumb-wrap").classList.add("missing");
    });
  }
}

function parseFilters() {
  try {
    return $("filters").value ? JSON.parse($("filters").value) : {};
  } catch (_) {
    alert("filters must be valid JSON");
    throw new Error("bad filters");
  }
}

$("textSearchBtn").onclick = async () => {
  try {
    const payload = await api(`${state.queryUrl}/v1/search/text`, {
      method: "POST",
      headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify({
        query: $("textQuery").value,
        top_k: Number($("topK").value),
        filters: parseFilters(),
      }),
    });
    renderResults(payload);
  } catch (e) {
    if (e.message !== "bad filters") alert(e.message);
  }
};

$("imageSearchBtn").onclick = async () => {
  const file = $("imageQuery").files[0];
  if (!file) return;
  try {
    const form = new FormData();
    form.append("file", file);
    form.append("top_k", $("topK").value);
    const filters = parseFilters();
    if (Object.keys(filters).length) form.append("filters", JSON.stringify(filters));
    const modifier = $("modifier").value.trim();
    const path = modifier ? "/v1/search/composed" : "/v1/search/image";
    if (modifier) form.append("modifier", modifier);
    const payload = await api(`${state.queryUrl}${path}`, {
      method: "POST",
      headers: headers(),
      body: form,
    });
    renderResults(payload);
  } catch (e) {
    if (e.message !== "bad filters") alert(e.message);
  }
};

initConn();
if (state.apiKey) refreshCatalog();
