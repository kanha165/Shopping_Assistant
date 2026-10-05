# AI Autonomous Shopping & Price Comparison Agent

An agentic AI shopping assistant that understands natural-language shopping requests, searches 6 Indian e-commerce platforms simultaneously, compares products, analyzes reviews, and walks you to the checkout — stopping for human approval before any payment.

---

## What It Does

- Understands queries like *"Find a 55-inch 4K TV under ₹50,000 with good reviews"*
- Searches **Amazon, Flipkart, Meesho, Myntra, Shopsy, Snapdeal** in parallel
- Normalizes all product data into a consistent schema
- Applies deterministic price/rating filters (no LLM for hard rules)
- Analyzes actual customer reviews for sentiment themes
- Ranks and shortlists the best matches with explanation
- Adds selected product to cart via browser automation
- **Always stops before payment** — human must complete checkout

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | LangGraph + LangChain |
| LLM | OpenAI GPT-4o or Google Gemini 1.5 Pro |
| Backend | FastAPI (async) |
| Browser Automation | Playwright |
| Database | PostgreSQL + SQLAlchemy (async) |
| Data Validation | Pydantic v2 |
| Frontend | Plain HTML + CSS + JavaScript |
| Logging | Loguru |

---

## Project Structure

```
shopping-agent/
├── backend/
│   ├── app/
│   │   ├── agent/             # LangGraph agent
│   │   │   ├── graph.py       # State machine with 6 nodes
│   │   │   ├── tools.py       # 9 agent tools
│   │   │   ├── runner.py      # run_shopping_agent() + SSE streaming
│   │   │   ├── cart_handler.py# Playwright cart automation
│   │   │   └── llm_provider.py# OpenAI / Gemini switcher
│   │   ├── scrapers/          # Platform scrapers
│   │   │   ├── base_scraper.py      # Shared Playwright base
│   │   │   ├── amazon_scraper.py
│   │   │   ├── flipkart_scraper.py
│   │   │   ├── meesho_scraper.py
│   │   │   ├── myntra_scraper.py
│   │   │   ├── shopsy_scraper.py
│   │   │   ├── snapdeal_scraper.py
│   │   │   └── scraper_manager.py   # Parallel search orchestrator
│   │   ├── api/               # FastAPI routes
│   │   │   ├── routes_auth.py       # /auth/register, /auth/login
│   │   │   ├── routes_search.py     # /search/, /search/stream (SSE)
│   │   │   ├── routes_products.py   # /products/, /cart/add, /checkout
│   │   │   └── routes_agent.py      # /agent/logs/
│   │   ├── models/            # SQLAlchemy DB models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── core/              # Config, DB, logger, security
│   ├── main.py                # Uvicorn entry point
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html             # Single-page UI
    ├── css/
    │   ├── style.css          # Layout, dark theme
    │   └── components.css     # Cards, modals, buttons
    └── js/
        ├── api.js             # All fetch() calls
        ├── state.js           # Global state
        ├── ui.js              # DOM rendering
        ├── search.js          # Search + SSE streaming
        ├── auth.js            # Login / register
        └── app.js             # Init + keyboard shortcuts
```

---

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL running locally (or any accessible instance)
- An OpenAI API key **or** a Google Gemini API key

---

### Step 1 — Clone & enter the project

```bash
git clone <your-repo-url>
cd shopping-agent
```

### Step 2 — Create Python virtual environment

```bash
cd backend
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

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Pick one LLM provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# PostgreSQL connection
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/shopping_agent
DATABASE_URL_SYNC=postgresql://postgres:yourpassword@localhost:5432/shopping_agent

# Change this to a random secret
SECRET_KEY=your-random-secret-key
```

### Step 6 — Create the database

```bash
# Connect to PostgreSQL and create the database
psql -U postgres -c "CREATE DATABASE shopping_agent;"
```

The app will auto-create all tables on first startup.

### Step 7 — Start the backend

```bash
# From inside the backend/ directory
python main.py
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`  
API docs at: `http://localhost:8000/api/docs`

### Step 8 — Open the frontend

Open `frontend/index.html` directly in your browser, **or** use VS Code Live Server extension (recommended for CORS to work correctly).

If using Live Server: right-click `index.html` → *Open with Live Server*  
It will open at `http://127.0.0.1:5500`

---

## Usage

### Basic Search

1. Type a shopping query in the search box:
   - *"Find a 55 inch 4K TV under ₹50,000 with good reviews"*
   - *"Samsung mobile under ₹20,000 with good camera"*
   - *"Nike running shoes size 9"*

2. Click **Search** or press `Enter`

3. Watch the **Agent Activity** panel on the left as the agent:
   - Parses your query into structured constraints
   - Searches all 6 platforms simultaneously
   - Filters by your budget and rating requirements
   - Analyzes reviews for top products
   - Generates a personalized recommendation

4. Browse results — use **Grid** or **Compare** view

5. Click any product to see full details, specifications, and review analysis

6. Click **Add to Cart** — agent navigates to cart and provides the checkout URL

7. **Complete payment yourself** on the platform — the agent never handles CVV, OTP, or passwords

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Enter` | Submit search |
| `Ctrl + /` | Focus search box |
| `Escape` | Close any open modal |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/platforms` | List supported platforms |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/search/` | Run full agent search |
| GET | `/api/search/stream` | SSE streaming search |
| GET | `/api/search/history` | User search history |
| GET | `/api/search/{id}` | Get search results by ID |
| GET | `/api/products/{id}` | Get product details |
| POST | `/api/products/cart/add` | Add product to cart |
| POST | `/api/products/checkout/handoff/{id}` | Get checkout URL |
| GET | `/api/agent/logs/{session_id}` | Agent activity logs |

Full interactive docs: `http://localhost:8000/api/docs`

---

## Agent Architecture

```
User Query
    │
    ▼
[Node 1] parse_query
    │  LLM extracts: category, max_price, min_rating, brand, size, keywords
    ▼
[Node 2] search_products
    │  asyncio.gather() → 6 platforms simultaneously
    │  Amazon · Flipkart · Meesho · Myntra · Shopsy · Snapdeal
    ▼
[Node 3] filter_products  ← DETERMINISTIC (no LLM)
    │  Hard reject: price > max_price, rating < min_rating
    │  Rank score = rating(40%) + review_volume(30%) + discount(30%)
    ▼
[Node 4] analyze_reviews
    │  Fetch top 3 products' reviews via Playwright
    │  LLM extracts: sentiment, positive/negative themes, defects
    ▼
[Node 5] generate_recommendation
    │  LLM writes explanation using only actual data (no fabrication)
    ▼
Results presented to user
    │
    └─► [User selects] → add_to_cart → STOP (human completes payment)
```

### Agent vs Deterministic Split

| Task | Who does it |
|---|---|
| Parse "under ₹50k" | LLM |
| Reject products above ₹50,000 | Deterministic code |
| Summarize review themes | LLM |
| Enforce minimum rating | Deterministic code |
| Decide which tool to call | LangGraph |
| Rank products by score | Deterministic formula |
| Explain recommendations | LLM |
| Handle payment | **Never — human only** |

---

## Supported Platforms

| Platform | Category | Notes |
|---|---|---|
| Amazon India | All | Electronics, fashion, grocery |
| Flipkart | All | Electronics, fashion, home |
| Meesho | Fashion, Home | Budget items |
| Myntra | Fashion | Clothing, footwear, accessories |
| Shopsy | All | Flipkart's budget platform |
| Snapdeal | All | Electronics, fashion |

---

## Security Notes

- Payment credentials (CVV, OTP, passwords) are **never** stored or handled
- Agent always stops at checkout and requires human approval
- Anti-bot detection is handled via rotating user-agents and human-like delays
- JWT tokens expire after 24 hours
- All user passwords are bcrypt hashed

---

## Troubleshooting

**Backend won't start**
- Make sure PostgreSQL is running: `pg_isready`
- Check `.env` database URL is correct
- Make sure the `shopping_agent` database exists

**Playwright errors**
- Run: `playwright install chromium --with-deps`
- On Windows, run the terminal as Administrator

**CORS errors in browser**
- Make sure `ALLOWED_ORIGINS` in `.env` includes your frontend URL
- Use Live Server (`127.0.0.1:5500`) not `file://`

**LLM errors**
- Verify your API key is correct in `.env`
- Check you have quota/credits remaining
- Try switching `LLM_PROVIDER` from `openai` to `google`

**Scraper returns 0 products**
- The platforms may have updated their HTML structure
- Try setting `PLAYWRIGHT_HEADLESS=False` in `.env` to watch the browser
- Check `logs/app.log` for detailed scraper errors

---

## Demo Query for Presentation

```
Find a 55 inch 4K TV under ₹50,000 with a rating above 4 stars and good reviews
```

This will demonstrate:
1. Query parsing → structured constraints
2. Multi-platform parallel search
3. Price filter (hard reject above ₹50,000)
4. Rating filter (hard reject below 4.0)
5. Review analysis for top 3 results
6. AI recommendation with evidence
7. Cart add → checkout handoff → human approval gate
