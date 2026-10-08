const API_URL = window.ENV?.API_URL || "http://127.0.0.1:8000";

// Nav Elements
const navScrape = document.getElementById("nav-scrape");
const navHistory = document.getElementById("nav-history");
const viewScrape = document.getElementById("view-scrape");
const viewHistory = document.getElementById("view-history");

// Scrape Elements
const form = document.getElementById("scrapeForm");
const urlInput = document.getElementById("urlInput");
const scrapeBtn = document.getElementById("scrapeBtn");
const btnLabel = document.getElementById("btnLabel");
const spinner = document.getElementById("spinner");
const errorMsg = document.getElementById("errorMsg");
const successMsg = document.getElementById("successMsg");
const scrapeResult = document.getElementById("scrapeResult");

// History Elements
const historyTbody = document.getElementById("historyTbody");
const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const clearSearchBtn = document.getElementById("clearSearchBtn");

// Modal Elements
const detailModal = document.getElementById("detailModal");
const closeModalBtn = document.getElementById("closeModalBtn");
const modalBody = document.getElementById("modalBody");

// --- Navigation ---
navScrape.addEventListener("click", () => switchView('scrape'));
navHistory.addEventListener("click", () => {
  switchView('history');
  loadHistory();
});

function switchView(view) {
  if (view === 'scrape') {
    viewScrape.classList.add("active");
    viewScrape.classList.remove("hidden");
    viewHistory.classList.remove("active");
    viewHistory.classList.add("hidden");
    navScrape.classList.add("active");
    navHistory.classList.remove("active");
  } else {
    viewHistory.classList.add("active");
    viewHistory.classList.remove("hidden");
    viewScrape.classList.remove("active");
    viewScrape.classList.add("hidden");
    navHistory.classList.add("active");
    navScrape.classList.remove("active");
  }
}

// --- Scrape Flow ---
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;

  resetMessages();
  setLoading(true);
  scrapeResult.classList.add("hidden");

  try {
    const res = await fetch(`${API_URL}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error: ${res.status}`);
    }

    const data = await res.json();
    showSuccess(data.message);
    renderPageDetails(data.data, scrapeResult);
    scrapeResult.classList.remove("hidden");
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
});

// --- History Flow ---
async function loadHistory(keyword = "") {
  try {
    const endpoint = keyword 
      ? `${API_URL}/search?keyword=${encodeURIComponent(keyword)}` 
      : `${API_URL}/pages`;
    
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error("Failed to load pages");
    const pages = await res.json();
    
    historyTbody.innerHTML = pages.length ? "" : `<tr><td colspan="6">No pages found.</td></tr>`;
    
    pages.forEach(p => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${p.id}</td>
        <td class="truncate" title="${escapeHtml(p.url)}"><a href="${escapeHtml(p.url)}" target="_blank">${escapeHtml(p.url)}</a></td>
        <td class="truncate" title="${escapeHtml(p.title || 'N/A')}">${escapeHtml(p.title || 'N/A')}</td>
        <td>${escapeHtml(p.status)}</td>
        <td>${new Date(p.created_at).toLocaleDateString()}</td>
        <td><button class="view-btn" onclick="viewPage(${p.id})">View</button></td>
      `;
      historyTbody.appendChild(tr);
    });
  } catch (err) {
    historyTbody.innerHTML = `<tr><td colspan="6" style="color:red">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

searchBtn.addEventListener("click", () => loadHistory(searchInput.value.trim()));
clearSearchBtn.addEventListener("click", () => {
  searchInput.value = "";
  loadHistory();
});
searchInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") loadHistory(searchInput.value.trim());
});

// --- Modal & Detailed View ---
window.viewPage = async function(id) {
  try {
    const res = await fetch(`${API_URL}/pages/${id}`);
    if (!res.ok) throw new Error("Failed to fetch page details");
    const page = await res.json();
    renderPageDetails(page, modalBody);
    detailModal.classList.remove("hidden");
  } catch(err) {
    alert("Error: " + err.message);
  }
};

closeModalBtn.addEventListener("click", () => detailModal.classList.add("hidden"));
window.addEventListener("click", (e) => {
  if (e.target === detailModal) detailModal.classList.add("hidden");
});

// --- Helpers ---
function renderPageDetails(page, container) {
  const c = page.content || { headings: {h1:[],h2:[],h3:[]}, paragraphs: [], links: [], images: [] };
  const h1 = c.headings?.h1 || [];
  const h2 = c.headings?.h2 || [];
  const h3 = c.headings?.h3 || [];
  const pList = c.paragraphs || [];
  const links = c.links || [];
  const images = c.images || [];
  const kw = page.keywords || [];

  container.innerHTML = `
    <h2>${escapeHtml(page.title || "Untitled")}</h2>
    <p><strong>URL:</strong> <a href="${escapeHtml(page.url)}" target="_blank">${escapeHtml(page.url)}</a></p>
    <p><strong>Status:</strong> ${escapeHtml(page.status)} | <strong>Date:</strong> ${new Date(page.created_at).toLocaleString()}</p>
    
    <div class="data-section">
      <h3>Meta Description</h3>
      <p>${escapeHtml(page.description || "No description found.")}</p>
    </div>

    <div class="data-section">
      <h3>Keywords Extract</h3>
      <div class="keywords">
        ${kw.length ? kw.map(k => `<span class="keyword-chip">${escapeHtml(k)}</span>`).join("") : "None"}
      </div>
    </div>

    <div class="data-section">
      <h3>Headings (H1, H2, H3 count: ${h1.length + h2.length + h3.length})</h3>
      <div style="max-height:100px; overflow-y:auto; border:1px solid #e5e7eb; padding: 0.5rem;">
        ${[...h1, ...h2, ...h3].map(h => `<p>• ${escapeHtml(h)}</p>`).join("") || "No headings"}
      </div>
    </div>

    <div class="data-section">
      <h3>Paragraphs (Count: ${pList.length})</h3>
      <div style="max-height:150px; overflow-y:auto; border:1px solid #e5e7eb; padding: 0.5rem;">
        ${pList.map(p => `<p style="margin-bottom:0.5rem;">${escapeHtml(p)}</p>`).join("") || "No paragraphs"}
      </div>
    </div>

    <div class="data-section">
      <h3>Links (Count: ${links.length})</h3>
      <div style="max-height:100px; overflow-y:auto; border:1px solid #e5e7eb; padding: 0.5rem;">
        ${links.map(l => `<p><a href="${escapeHtml(l)}" target="_blank">${escapeHtml(l)}</a></p>`).join("") || "No links"}
      </div>
    </div>

    <div class="data-section">
      <h3>Images (Count: ${images.length})</h3>
      <div style="max-height:100px; overflow-y:auto; border:1px solid #e5e7eb; padding: 0.5rem;">
        ${images.map(img => `<p>${escapeHtml(img)}</p>`).join("") || "No images"}
      </div>
    </div>
  `;
}

function setLoading(isLoading) {
  scrapeBtn.disabled = isLoading;
  spinner.classList.toggle("hidden", !isLoading);
  btnLabel.textContent = isLoading ? "Scraping..." : "Scrape";
}

function resetMessages() {
  errorMsg.classList.add("hidden");
  successMsg.classList.add("hidden");
  errorMsg.textContent = "";
  successMsg.textContent = "";
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.remove("hidden");
}

function showSuccess(msg) {
  successMsg.textContent = msg;
  successMsg.classList.remove("hidden");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}