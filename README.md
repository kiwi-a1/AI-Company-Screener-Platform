# Equity Research Workspace

A multi-company stock and corporate financial analysis platform powered by Yahoo Finance (via `yfinance`),
with a persistent, context-aware AI financial analyst built on Claude.

- **Global search** by company name or ticker; any Yahoo symbol (`AAPL`, `BRK-B`, `RELIANCE.NS`, `^GSPC`).
- **Live market header**: price, daily change, pre/after-hours quote and market state, auto-refreshed.
- **Six sections**: Summary · News · Statistics · Historical Data · Financials · Holders.
- **AI analyst sidebar**: follows the selected company and section, calls Yahoo data tools, runs deterministic
  calculations, searches the web, and cites sources with dates.
- **Honest data**: every section shows retrieval time; unavailable values show “—”, never 0; failed refreshes fall
  back to the last good data with a visible warning and a Retry button.

## Deploy online in 10 minutes (no coding)

1. Put this code in a GitHub repository.
2. Go to **share.streamlit.io**, sign in with GitHub, click **Create app**, choose the repository,
   branch `main`, main file `app.py`.
3. Open **Advanced settings → Secrets** and paste ONE of these (with your real key inside the quotes):
   ```toml
   GEMINI_API_KEY = "your-new-gemini-key"
   # or
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Click **Deploy**. Yahoo Finance data needs no key. You'll get a link like `https://your-app.streamlit.app`.

The chatbot uses Claude if an Anthropic key is set, otherwise Gemini. Never put keys in the code or share them in chat.

## Quick start (on your own computer)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY to enable the AI analyst
streamlit run app.py
```

Open http://localhost:8501. Deep links work: `?s=MSFT&tab=Financials`.

Docker:

```bash
docker build -t equity-workspace .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=... equity-workspace
```

On Streamlit Community Cloud, put `ANTHROPIC_API_KEY` in the app's Secrets.

### Configuration (`.env` or environment)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Enables the AI analyst with Claude (preferred if both keys set) |
| `GEMINI_API_KEY` | — | Enables the AI analyst with Google Gemini |
| `GEMINI_MODEL` | `gemini-flash-latest` | Gemini model |
| `ANALYST_MODEL` | `claude-opus-5-5` | Claude model for the analyst |
| `ANALYST_EFFORT` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` – depth vs. cost |
| `QUOTE_REFRESH_SECONDS` | `30` | Live header refresh interval and quote cache TTL |
| `BENCHMARK_SYMBOL` | `^GSPC` | Benchmark for performance comparisons |
| `DEFAULT_SYMBOL` | `AAPL` | Company shown on first load |

## Architecture

```
app.py                  shell: search, live header, section nav, routing, AI sidebar
sections/               summary, news, statistics, historical_data, financials, holders
components/             global_header, search, quote_cards, metric_table, news_feed,
                        financial_chart, data_states, sidebar (AI chat)
services/               cache (TTL + retries + stale fallback), market_data, history, news,
                        financials, ownership, statistics (metric groups), metrics (calculations)
ai/                     assistant (agent loop), tools, prompts, context_manager, web_search, citations
utils/                  formatting, validation, normalization
tests/                  unit tests, AppTest smoke tests, synthetic Yahoo fake for offline runs
```

> The section modules live in `sections/` rather than `pages/`: Streamlit treats a `pages/` folder as
> automatic multipage navigation, which would break the single-workspace layout and the persistent chat.

**Data flow.** Every service returns a `DataResult(data, fetched_at, stale, error, cached)`. Raw yfinance payloads
are normalized once (`utils/normalization.py`): numbers become `float | None`, epochs become datetimes, statement rows
use stable yfinance keys mapped to the spec's line items, and news handles both yfinance schemas with http(s)-only
links. `services/metrics.py` holds all derived calculations (margins, growth, CAGR, returns vs benchmark, ratios,
comparisons) and returns `None` — never 0 — for missing inputs or zero denominators; balance-sheet ratios only
combine periods that match exactly.

**AI analyst.** `ai/assistant.py` runs a streaming tool-use loop with Claude (adaptive thinking, configurable effort,
prompt caching, server-side refusal fallback). Tools in `ai/tools.py` (strict schemas, validated inputs) wrap the same
services the UI uses: company snapshot, key statistics, price history & returns, financial statements, computed
ratios, holders, news, multi-company comparison, a deterministic calculator, and ticker search. Claude's server-side
`web_search` handles external research. Each turn carries an app-context note (selected company, active section,
filters, visible figures) as a mid-conversation system message, so the conversation persists across navigation and
ticker changes. Answers list Yahoo data retrieval times and web sources (cited first) under a “Sources & steps”
expander. News and web content are treated as untrusted data.

## Tests

```bash
pytest -q
```

Covers metric calculations, normalization, formatting/validation, caching/retry/stale behavior, data services with
mocked yfinance, every section rendered through Streamlit's `AppTest`, the AI tools, citations, and the agent loop
with a scripted Claude client. To click around the UI without network access, run it on **synthetic** data:

```bash
python -m tests.run_offline
```

## Data source & terms

`yfinance` is an unofficial interface to Yahoo Finance. Field availability, history depth, news metadata and
extended-hours data vary by ticker; quotes may be delayed. Review Yahoo's terms before redistributing data, and
use a licensed market-data provider if you need contractual uptime or real-time data. Nothing in this app is
investment advice.
