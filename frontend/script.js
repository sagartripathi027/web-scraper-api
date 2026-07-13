const API_URL = "http://127.0.0.1:8000/scrape";

// Grab all the DOM elements we need once, up front.
const form = document.getElementById("scrapeForm");
const urlInput = document.getElementById("urlInput");
const scrapeBtn = document.getElementById("scrapeBtn");
const btnLabel = document.getElementById("btnLabel");
const spinner = document.getElementById("spinner");
const errorMsg = document.getElementById("errorMsg");
const successMsg = document.getElementById("successMsg");
const summary = document.getElementById("summary");
const jobCount = document.getElementById("jobCount");
const cardsGrid = document.getElementById("cardsGrid");

// Handle the form submit (the "Scrape Jobs" button).
form.addEventListener("submit", async (event) => {
  event.preventDefault(); // stop the page from reloading
  const url = urlInput.value.trim();
  if (!url) return;

  resetMessages();
  setLoading(true);

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    
    if (!response.ok) {
      const errorBody = await safeJson(response);
      const detail = errorBody?.detail || `Request failed with status ${response.status}`;
      throw new Error(detail);
    }

    const result = await response.json();
    renderResult(result, url);
  } catch (err) {
    

    showError(err.message || "Something went wrong while scraping this URL.");
    summary.classList.add("hidden");
    cardsGrid.innerHTML = "";
  } finally {
    setLoading(false);
  }
});

function renderResult(result, originalUrl) {
  const page = result.data;
  const domain = getDomain(originalUrl);

  showSuccess(result.message || "Page scraped successfully.");

  jobCount.textContent = "1";
  summary.classList.remove("hidden");

  const skills = Array.isArray(page.keywords) ? page.keywords : [];

  const card = document.createElement("article");
  card.className = "job-card";
  card.innerHTML = `
    <h3 class="job-card__title">${escapeHtml(page.title || "Untitled page")}</h3>
    <p class="job-card__company">${escapeHtml(domain)}</p>

    <div class="job-card__row"><span>Location</span><span class="job-card__placeholder">Not specified</span></div>
    <div class="job-card__row"><span>Salary</span><span class="job-card__placeholder">Not specified</span></div>
    <div class="job-card__row"><span>Experience</span><span class="job-card__placeholder">Not specified</span></div>
    <div class="job-card__row"><span>Source</span><span>${escapeHtml(domain)}</span></div>

    <div class="job-card__skills">
      ${
        skills.length
          ? skills.map((kw) => `<span class="skill-chip">${escapeHtml(kw)}</span>`).join("")
          : `<span class="job-card__placeholder">No keywords extracted</span>`
      }
    </div>

    <a class="job-card__apply" href="${escapeHtml(originalUrl)}" target="_blank" rel="noopener noreferrer">
      Apply / View Source
    </a>
  `;

  cardsGrid.innerHTML = "";
  cardsGrid.appendChild(card);
}

// ---------- Small helper functions ----------

function setLoading(isLoading) {
  scrapeBtn.disabled = isLoading;
  spinner.classList.toggle("hidden", !isLoading);
  btnLabel.textContent = isLoading ? "Scraping..." : "Scrape Jobs";
}

function resetMessages() {
  errorMsg.classList.add("hidden");
  successMsg.classList.add("hidden");
  errorMsg.textContent = "";
  successMsg.textContent = "";
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.classList.remove("hidden");
  successMsg.classList.add("hidden");
}

function showSuccess(message) {
  successMsg.textContent = message;
  successMsg.classList.remove("hidden");
  errorMsg.classList.add("hidden");
}

// Extracts just the hostname (e.g. "example.com") from a full URL,
// used to display a "Company"/"Source" value.
function getDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// Safely parse JSON without throwing if the body is empty/invalid.
async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

// Basic escaping so scraped text can never break the page's HTML.
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}