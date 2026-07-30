/* =============================================================
   Activity Tracker Dashboard — Frontend Logic
   ============================================================= */

const API = "";   // same origin

// --- Utility: fetch wrapper -----------------------------------------
async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// --- Toast -----------------------------------------------------------
let toastTimer;
function showToast(msg, type = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = "toast"; }, 3200);
}

// --- Stat helpers ----------------------------------------------------
function setStat(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// --- Keywords --------------------------------------------------------
let allKeywords = [];

function renderKeywords(filter = "") {
  const list = document.getElementById("kw-list");
  const badge = document.getElementById("kw-count-badge");
  const q = filter.toLowerCase().trim();
  const visible = q ? allKeywords.filter(k =>
    k.keyword.toLowerCase().includes(q) || (k.category || "").toLowerCase().includes(q)
  ) : allKeywords;

  badge.textContent = allKeywords.length;
  setStat("stat-keywords", allKeywords.length);

  if (visible.length === 0) {
    list.innerHTML = `<div class="empty-state">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
      <span>${q ? "No matches found" : "No keywords yet — add someone above"}</span>
    </div>`;
    return;
  }

  list.innerHTML = visible.map(k => `
    <div class="kw-item" data-keyword="${escHtml(k.keyword)}">
      <div class="kw-info">
        <div class="kw-name">${escHtml(k.keyword)}</div>
        ${k.category ? `<div class="kw-cat"><span class="category-chip">${escHtml(k.category)}</span></div>` : ""}
      </div>
      <button class="btn btn-danger delete-btn" data-kw="${escHtml(k.keyword)}" title="Remove">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
      </button>
    </div>
  `).join("");

  // Attach delete listeners
  list.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const kw = btn.dataset.kw;
      if (!confirm(`Remove "${kw}" from tracking?`)) return;
      btn.disabled = true;
      try {
        await api(`/api/keywords/${encodeURIComponent(kw)}`, { method: "DELETE" });
        allKeywords = allKeywords.filter(k => k.keyword !== kw);
        renderKeywords(document.getElementById("kw-search").value);
        showToast(`"${kw}" removed`);
      } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
      }
    });
  });
}

async function loadKeywords() {
  const list = document.getElementById("kw-list");
  list.innerHTML = `<div class="loading-state"><div class="spinner"></div><span>Loading…</span></div>`;
  try {
    allKeywords = await api("/api/keywords");
    renderKeywords();
  } catch (e) {
    list.innerHTML = `<div class="empty-state">Failed to load keywords: ${escHtml(e.message)}</div>`;
  }
}

// --- Settings --------------------------------------------------------
async function loadSettings() {
  try {
    const s = await api("/api/settings");
    const emailInput = document.getElementById("email-input");
    emailInput.placeholder = s.notification_email_to || "your@email.com";
    emailInput.value = s.notification_email_to || "";
    setStat("stat-email", s.notification_email_to || "Not set");
  } catch (e) {
    console.warn("Settings load failed:", e.message);
  }
}

// --- Pipeline run status -------------------------------------------- 
let lastRunTime = null;

function setStatus(state) {
  const badge = document.getElementById("pipeline-status");
  const dot = badge.querySelector(".status-dot");
  const text = badge.querySelector(".status-text");
  dot.className = "status-dot " + (state === "running" ? "running" : state === "error" ? "error" : "");
  text.textContent = state === "running" ? "Running…" : state === "error" ? "Error" : "Idle";
}

// --- HTML escaping utility -------------------------------------------
function escHtml(str) {
  return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// --- Event bindings -------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {

  // Initial data load
  loadKeywords();
  loadSettings();

  // Search filter
  document.getElementById("kw-search").addEventListener("input", e => {
    renderKeywords(e.target.value);
  });

  // Add keyword form
  document.getElementById("add-kw-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const kwInput = document.getElementById("kw-input");
    const catInput = document.getElementById("cat-input");
    const btn = document.getElementById("add-kw-btn");
    const kw = kwInput.value.trim();
    const cat = catInput.value.trim();
    if (!kw) return;

    btn.disabled = true;
    btn.innerHTML = `<div class="spinner" style="width:13px;height:13px;border-width:2px"></div> Adding…`;
    try {
      await api("/api/keywords", {
        method: "POST",
        body: JSON.stringify({ keyword: kw, category: cat }),
      });
      allKeywords.unshift({ keyword: kw, category: cat });
      kwInput.value = "";
      catInput.value = "";
      renderKeywords(document.getElementById("kw-search").value);
      showToast(`"${kw}" added to tracking ✓`);
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add`;
    }
  });

  // Email form
  document.getElementById("email-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const emailInput = document.getElementById("email-input");
    const btn = document.getElementById("save-email-btn");
    const email = emailInput.value.trim();
    if (!email) return;

    btn.disabled = true;
    btn.textContent = "Saving…";
    try {
      await api("/api/settings/email", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setStat("stat-email", email);
      showToast("Alert email updated ✓");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Save";
    }
  });

  // Run pipeline
  document.getElementById("run-pipeline-btn").addEventListener("click", async () => {
    const btn = document.getElementById("run-pipeline-btn");
    btn.disabled = true;
    btn.innerHTML = `<div class="spinner" style="width:13px;height:13px;border-width:2px"></div> Running…`;
    setStatus("running");

    try {
      const result = await api("/api/pipeline/run", { method: "POST" });
      const stats = result.stats || [];
      const totalArticles = stats.reduce((s, r) => s + r.articles_found, 0);
      const totalMatched  = stats.reduce((s, r) => s + r.articles_matched, 0);
      const totalEmails   = stats.reduce((s, r) => s + r.emails_sent, 0);

      const now = new Date();
      lastRunTime = now.toLocaleTimeString();
      setStat("stat-last-run", lastRunTime);

      const msg = totalMatched > 0
        ? `✓ Found ${totalArticles} articles, ${totalMatched} matched, ${totalEmails} alert(s) sent`
        : totalArticles > 0
          ? `✓ Scraped ${totalArticles} articles — no keyword matches`
          : "✓ Pipeline completed — no new articles found";

      showToast(msg, totalMatched > 0 ? "success" : "success");
      setStatus("idle");
    } catch (e) {
      showToast("Pipeline error: " + e.message, "error");
      setStatus("error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Now`;
    }
  });

});
