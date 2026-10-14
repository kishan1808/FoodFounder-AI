# FoodFounder AI

**A simple AI assistant for small-scale food entrepreneurs.**

FoodFounder AI helps you move from a product idea to preliminary formulation guidance,
production cost estimation, packaging considerations, and food-processing guidance —
built for first-time food entrepreneurs (Indian context: ₹, FSSAI).

## Features

| Feature | What it does |
|---|---|
| **Product setup** | Enter product name, category, batch size, and budget |
| **Cost calculator** | Ingredient costs, total production cost, cost per packet, profit per packet, margin %, batch profit — with input validation |
| **AI chat assistant** | Real LLM chat (Google Gemini free tier) about formulation, packaging, processing, costing concepts, and food safety |
| **Guidance checklists** | Packaging, processing, and product-trial checklists + verified official FSSAI links |
| **Product summary** | One-click downloadable Markdown report of your product, costs, chat advice, and next steps |

**Important:** all calculations and AI answers are **estimates for planning**. They are not
lab-validated, not legal advice, and do not certify regulatory compliance. Verify with
suppliers, trials, qualified experts, and official FSSAI resources before selling.

## Tech stack

- Python 3.14 (3.10+ should work)
- Streamlit (web UI)
- `google-genai` (Google Gemini API for the chatbot)
- Pandas (ingredient table rendering)
- Pure-Python calculation and report modules (unit-tested, no framework lock-in)
- Standard-library `unittest` for all tests (no extra test dependency)

## Project structure

```
FoodFounder AI/
├── app.py                  # Streamlit UI (3 pages: Home, Cost Calculator, AI Guidance)
├── services/
│   ├── __init__.py
│   ├── calculator.py       # Cost calculation engine (pure Python)
│   ├── ai_assistant.py     # Gemini chatbot logic (pure Python, injectable client)
│   ├── guidance.py         # Packaging/process/trial checklists + verified FSSAI links
│   └── report.py           # Downloadable Markdown summary generator
├── tests/
│   ├── test_calculator.py  # 19 unit tests for calculations
│   ├── test_ai_assistant.py# 17 tests for chat logic (fake client, no network)
│   ├── test_guidance.py    # 9 tests for checklists and links
│   ├── test_report.py      # 6 tests for the summary report
│   └── test_app.py         # 7 UI/end-to-end tests (Streamlit AppTest, no browser)
├── .streamlit/
│   ├── config.toml         # non-secret Streamlit config (theme)
│   └── secrets.toml        # your API key goes here (gitignored)
├── requirements.txt
├── .gitignore              # excludes venv/, .env, .streamlit/secrets.toml, caches
└── venv/                   # local virtual environment (not committed)
```

## Setup (Windows PowerShell)

```powershell
cd "C:\Users\Kishan Soni\Desktop\FoodFounder AI"
python -m venv venv                # already exists — skip if venv/ is present
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Configure the AI chatbot (free)

The chatbot uses the **Google Gemini API free tier** (no credit card).

1. Get a free API key: https://aistudio.google.com/apikey
2. Create `.streamlit/secrets.toml` (already excluded from Git) with:
   ```toml
   GEMINI_API_KEY = "paste-your-key-here"
   ```
   Or set it for the current PowerShell session only:
   ```powershell
   $env:GEMINI_API_KEY = "paste-your-key-here"
   ```
3. Restart the app. The AI Guidance page will show "API key detected".

Without a key, the calculator, checklists, and report all still work; the chat shows
friendly setup instructions.

## Run the app

```powershell
cd "C:\Users\Kishan Soni\Desktop\FoodFounder AI"
.\venv\Scripts\activate
streamlit run app.py
```

Open http://localhost:8501 in your browser. Stop with `Ctrl+C`.

## Run the tests

```powershell
cd "C:\Users\Kishan Soni\Desktop\FoodFounder AI"
.\venv\Scripts\activate
python -m unittest discover -s tests -t . -v
```

Expected: `Ran 58 tests` … `OK` (no network or API key required).

## 5-minute demo script (banana chips)

1. **Home / Product Setup** — name: `Banana Chips`, category: `Snacks`,
   batch size: `10` kg → click **Start**.
2. **Cost Calculator** — click **Load banana chips example** to fill sample ingredients,
   then **Calculate costs**.
3. Show results: total production cost **₹1,224.00**, cost/packet **₹30.60**,
   profit/packet **₹19.40**, margin **38.8%**, batch profit **₹776.00**.
4. Change selling price to `40` and recalculate → margin drops to ~23.5% (show live what-if).
5. **AI Guidance** — ask: "How should I package banana chips to keep them crisp?"
   (needs API key; without a key, show the friendly setup message instead).
6. Show the **Packaging / Processing / Trials / FSSAI** checklist tabs.
7. Click **Download summary (Markdown)** and open the file — show the full report.

## Deploy free (Streamlit Community Cloud)

Deployment needs your own accounts (I cannot create them for you):

1. Create a GitHub repository and push this project (exclude `venv/` — already in `.gitignore`):
   ```powershell
   cd "C:\Users\Kishan Soni\Desktop\FoodFounder AI"
   git init
   git add .
   git commit -m "FoodFounder AI hackathon prototype"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/foodfounder-ai.git
   git push -u origin main
   ```
2. Open https://share.streamlit.io/ → **Deploy an app** → pick the repo → main branch,
   `app.py`.
3. In the app's **Advanced settings → Secrets**, paste:
   ```toml
   GEMINI_API_KEY = "your-key"
   ```
4. Deploy. Streamlit Cloud installs `requirements.txt` automatically.

## Known limitations

- Costs exclude wastage, taxes, transport, retailer margins, commissions, etc.,
  unless you add them as "other expenses".
- Shelf-life, safety, nutrition, and licensing must be verified by trials, labs,
  experts, and official FSSAI sources — the app does not certify any of these.
- The Gemini free tier has per-project rate limits (shown in AI Studio); heavy use
  may hit temporary limits.
- Storage is in-memory: refreshing the browser clears the session (fine for a demo).
