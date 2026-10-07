# AI Shopping & Price Comparison Agent

An agentic AI shopping assistant that understands natural-language requests, searches Amazon, Flipkart, and Snapdeal simultaneously, compares products, analyzes reviews, and hands off to the user for checkout — the agent never touches payment credentials.

---

## What It Does

- Understands queries like *"Find a 55-inch 4K TV under ₹50,000 with good reviews"*
- Searches **Amazon, Flipkart, Snapdeal** (+ Meesho, Myntra, Shopsy via RapidAPI / Playwright fallback)
- Normalizes all product data into a consistent schema
- Applies deterministic price/rating filters (no LLM for hard rules)
- Analyzes actual customer reviews for sentiment themes
- Ranks and shortlists the best matches with an explanation
- **Always stops before payment** — human must complete checkout

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | LangGraph + LangChain |
| LLM | OpenAI GPT-4o or Google Gemini 2.5 Flash |
| Backend | FastAPI (async, stateless, no DB) |
| Browser Automation | Playwright (cart handoff + Meesho/Myntra fallback) |
| Data Validation | Pydantic v2 |
| Frontend | Plain HTML + CSS + JavaScript |
| Logging | Loguru |

---

## Project Structure

```
shopping-agent/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── graph.py          # LangGraph state machine (7 nodes)
│   │   │   ├── tools.py          # Agent tools (query parser, search, filter, reviews, etc.)
│   │   │   ├── runner.py         # run_shopping_agent() + SSE streaming
│   │   │   ├── cart_handler.py   # Cart URL handoff (no Playwright needed)
│   │   │   └── llm_provider.py   # OpenAI / Gemini / Ollama switcher
│   │   ├── scrapers/
│   │   │   ├── base_scraper.py         # Shared httpx + BeautifulSoup base
│   │   │   ├── amazon_scraper.py
│   │   │   ├── flipkart_scraper.py
│   │   │   ├── snapdeal_scraper.py
│   │   │   ├── meesho_scraper.py       # RapidAPI or Playwright fallback
│   │   │   ├── myntra_scraper.py       # RapidAPI or Playwright fallback
│   │   │   ├── shopsy_scraper.py
│   │   │   ├── playwright_runner.py    # Thread-pool Playwright executor
│   │   │   └── scraper_manager.py      # Parallel search orchestrator
│   │   ├── api/
│   │   │   └── routes_search.py        # POST /search/, GET /search/stream (SSE)
│   │   ├── schemas/
│   │   │   ├── product.py
│   │   │   └── search.py
│   │   └── core/
│   │       ├── config.py               # Settings from .env
│   │       └── logger.py               # Loguru setup
│   ├── main.py                         # Uvicorn entry point
│   ├── requirements.txt
│   └── .env
└── frontend/
    ├── index.html
    ├── css/
    │   └── style.css
    └── js/
        ├── api.js
        ├── state.js
        ├── ui.js
        ├── search.js
        ├── purchase.js
        └── app.js
```

---

## Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key **or** a Google Gemini API key

No database required — the backend is fully stateless.

---

### Step 1 — Clone & enter the project

```bash
git clone <your-repo-url>
cd shopping-agent/backend
```

### Step 2 — Create Python virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Install Playwright browsers

```bash
playwright install chromium --with-deps
```

### Step 5 — Configure environment

Edit `.env` and fill in:

```env
# Pick one LLM provider
LLM_PROVIDER=google
GOOGLE_API_KEY=your-gemini-key-here

# Or use OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-key-here

# Optional: RapidAPI key enables Meesho + Myntra results
# RAPIDAPI_KEY=your-rapidapi-key
```

### Step 6 — Start the backend

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`
API docs at: `http://localhost:8000/api/docs`

### Step 7 — Open the frontend

Open `frontend/index.html` in your browser, or use VS Code Live Server (recommended to avoid CORS issues).

---

## Usage

1. Type a shopping query in the search box:
   - *"Samsung Galaxy S24 256GB cheapest price"*
   - *"Laptop under ₹60,000 for coding"*
   - *"Best 4K Smart TV under ₹50,000"*

2. Click **Search** — the AI Agent Activity panel shows real-time progress

3. Browse results in Grid, List, or Compare view

4. Click **Buy Now** — the agent opens the product page on the marketplace

5. **Complete payment yourself** — the agent never handles CVV, OTP, or passwords

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/platforms` | List supported platforms |
| POST | `/api/search/` | Run full agent search |
| GET | `/api/search/stream` | SSE streaming search |

Full interactive docs: `http://localhost:8000/api/docs`

---

## Agent Pipeline

```
User Query
    │
    ▼
[1] parse_query        — LLM extracts category, budget, brand, specs
    │
    ▼
[2] search_products    — asyncio.gather() across Amazon, Flipkart, Snapdeal
    │
    ▼
[3] deduplicate        — match same product across platforms (deterministic)
    │
    ▼
[4] calculate_cost     — price + shipping total (deterministic)
    │
    ▼
[5] filter_products    — hard reject by price/rating, rank by score (deterministic)
    │
    ▼
[6] analyze_reviews    — fetch + LLM sentiment for top 3 products
    │
    ▼
[7] generate_recommendation — LLM writes explanation from actual data only
    │
    ▼
Results → user selects → Buy Now → opens marketplace page → human pays
```

---

## Supported Platforms

| Platform | Method | Notes |
|---|---|---|
| Amazon India | httpx + BeautifulSoup | Reliable |
| Flipkart | httpx + BeautifulSoup | Reliable |
| Snapdeal | httpx + BeautifulSoup | Reliable |
| Meesho | RapidAPI or Playwright | Often blocked without RapidAPI key |
| Myntra | RapidAPI or Playwright | Often blocked without RapidAPI key |
| Shopsy | httpx + BeautifulSoup | Flipkart budget platform |

---

## Troubleshooting

**Backend won't start**
- Check `.env` has a valid `LLM_PROVIDER` and API key

**Playwright errors**
- Run: `playwright install chromium --with-deps`
- On Windows, run the terminal as Administrator

**CORS errors in browser**
- Use Live Server (`127.0.0.1:5500`) instead of opening `file://` directly

**LLM errors**
- Verify your API key is correct in `.env`
- Check you have quota/credits remaining
- Try switching `LLM_PROVIDER` from `openai` to `google`

**Scraper returns 0 products**
- The platforms may have updated their HTML structure
- Set `PLAYWRIGHT_HEADLESS=False` in `.env` to debug visually
- Check `logs/app.log` for scraper errors
