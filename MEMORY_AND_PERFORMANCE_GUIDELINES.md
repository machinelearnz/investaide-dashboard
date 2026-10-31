# Performance & Memory Optimization Design Guidelines

This document outlines architectural design rules and best practices for developing and deploying data-intensive Python/Django web applications with Plotly and external financial scraping on memory-constrained hosting tiers (e.g., Render 512 MB Free Tier).

---

## 1. Gunicorn Concurrency & Process Model

### The Problem
* Gunicorn's default multi-process pre-fork model (`workers = 2..4`) spawns multiple distinct Python interpreter processes in operating system RAM.
* In heavy analytics applications loading libraries like `pandas`, `numpy`, `plotly`, `scipy`, and `yfinance`, a single worker's base resident memory easily consumes **200 MB – 250 MB**.
* Running 2 workers immediately consumes **450 MB – 500 MB** at boot before any HTTP request is even handled. Any minor data parsing spike exceeds 512 MB, triggering Linux Kernel OOM killer (`SIGKILL`).

### The Design Rule
* **Single Process, Multi-Threaded (`gthread`):** Use 1 worker with multiple threads. Threads share the single Python interpreter heap and loaded library binaries in memory, keeping base memory consumption static.
* **Proactive Worker Recycling:** Memory fragmentation naturally occurs in Python after large DataFrame allocations and JSON operations. Recycle workers periodically so the OS can reclaim fragmented pages.
* **Extended Timeouts for External APIs:** External scraping or financial API calls can take 10–30s.

**Standard Production Command:**
```bash
gunicorn core.wsgi:application \
  --worker-class gthread \
  --workers 1 \
  --threads 4 \
  --max-requests 500 \
  --max-requests-jitter 50 \
  --timeout 120 \
  --keep-alive 5
```

**Environment Variables (`render.yaml`):**
```yaml
envVars:
  - key: WEB_CONCURRENCY
    value: "1"
```

---

## 2. Plotly HTML Bloat Elimination (The 99% Rule)

### The Problem
* By default, `plotly.offline.plot(fig, output_type='div')` has `include_plotlyjs=True`.
* This embeds the entire **3.5 MB unminified `plotly.js` library** inside every single chart container.
* If a page has 8 charts, the server generates and concatenates **8 identical copies of `plotly.js`**, creating a single HTML response of **~33 Megabytes**!
* Effects:
  1. High server RAM allocation during Django template rendering.
  2. Severe network latency (downloading 33 MB takes 5–10s).
  3. Client browser tab freezing as the JavaScript engine compiles 8 copies of `plotly.js`.

### The Design Rule
1. **Load Plotly ONCE in the Base Template via CDN:**
   In `core/templates/includes/scripts.html` (or `<head>` of `base.html`):
   ```html
   <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
   ```
   *The browser downloads the minified script once and caches it permanently.*

2. **Always Pass `include_plotlyjs=False` in Python:**
   ```python
   # Correct: Generates only the HTML div and data trace (~15 KB)
   chart_div = plot(fig, output_type='div', include_plotlyjs=False)
   ```
3. **Result:** Page HTML response shrinks from **33 MB down to ~250 KB** (99% reduction).

---

## 3. Dependency Discipline & Container Pruning

### The Problem
* Boilerplate templates or legacy code often retain heavy binary packages (`opencv-python`, `camelot-py`, `matplotlib`, `Flask`, `celery`, `SQLAlchemy`) that are never imported.
* Packages like `opencv-python` install C++ shared objects and large binaries into the container, inflating build times and baseline memory.

### The Design Rule
* Regularly audit `requirements.txt` against actual imports in the codebase:
  ```bash
  # Check if package is actually imported anywhere:
  grep -rn "import cv2" app/ core/
  ```
* Remove all legacy dependencies not used by the runtime application.
* Keep only strictly required libraries.

---

## 4. Lazy Loading & Garbage Collection

### The Problem
* Top-level imports of heavy machine learning / statistical packages (e.g. `scikit-learn`, `TSNE`, `KMeans`) load hundreds of internal Cython modules and arrays immediately upon server boot, even if that specific endpoint is rarely accessed.

### The Design Rule
1. **Lazy Imports for Heavy Sub-Modules:**
   Move imports inside the specific functions that execute them:
   ```python
   def ia_get_clusters(pret_df, ncluster):
       from sklearn.cluster import KMeans
       from sklearn.manifold import TSNE
       # ... execute clustering ...
   ```
2. **Explicit Garbage Collection:**
   After processing large DataFrames, CSVs, or multi-chart payloads in views:
   ```python
   import gc

   def index(request):
       # ... compute analytics ...
       resp = render(request, "index.html", context)
       gc.collect()  # Immediately free unreachable objects
       return resp
   ```

---

## 5. Resilient Financial Scraping on Cloud Datacenter IPs

### The Problem
* Free cloud services (Render, Railway, Heroku) run inside major cloud provider datacenters (AWS, Google Cloud).
* Financial endpoints (e.g., Yahoo Finance `v10/finance/quoteSummary`) apply Cloudflare/Akamai bot detection, blocking standard Python `requests` and `urllib` from datacenter IPs with `401 Unauthorized` or `429 Too Many Requests`.
* Additionally, Yahoo's `quoteSummary` requires both an `A3` tracking cookie and an authenticated session `crumb`.

### The Design Rule
* Use `curl_cffi` to impersonate real browser TLS fingerprints (e.g., `impersonate="chrome"`).
* Negotiate cookies and crumbs sequentially before querying data endpoints:
  ```python
  from curl_cffi import requests as cffi_req

  sess = cffi_req.Session(impersonate="chrome")
  # 1. Fetch cookie:
  sess.get("https://fc.yahoo.com", timeout=4)
  # 2. Fetch authenticated crumb:
  crumb_res = sess.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=4)
  crumb = crumb_res.text.strip()
  # 3. Fetch summary with crumb:
  res = sess.get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?crumb={crumb}&modules=financialData,defaultKeyStatistics,summaryDetail", timeout=5)
  ```
* Always maintain `t.fast_info` as a fallback for Market Cap and Last Price, as `/v8/` chart endpoints rarely block.
