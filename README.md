# morning-brief

## Gemini API Key Setup (after project/key rotation)

This project calls Gemini with an API key from environment variables.

The app reads:
- `GEMINI_API_KEY` (primary)
- `GOOGLE_API_KEY` (fallback)
- `GEMINI_MODEL` (optional, default: `gemini-2.5-flash`)

### 1) Enable the correct API on the key's project

In Google Cloud Console, select the **same project that owns your new API key**, then enable:
- **Generative Language API** (`generativelanguage.googleapis.com`)

If you already enabled it, wait a few minutes for propagation.

### 2) Create/get an API key

Use either:
- Google AI Studio key, or
- Google Cloud API key from that same enabled project.

### 3) Update GitHub Actions secret

In your repository:
- `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`
- Name: `GEMINI_API_KEY`
- Value: your new key

If the secret already exists, edit and replace the value.

### 3.1) (Optional) Set model override in GitHub

If you want to pin a specific model for CI:
- `Settings` -> `Secrets and variables` -> `Actions` -> `Variables` -> `New repository variable`
- Name: `GEMINI_MODEL`
- Value example: `gemini-2.5-flash`

### 3.2) (Optional) Todoist tasks/events integration

To include daily Todoist tasks in the brief:
- Add repository secret: `TODOIST_API_TOKEN`
  - Use raw token only (do not prefix with `Bearer` and do not wrap in quotes)
- Add repository variables (optional):
  - `TODOIST_FILTER` (example: `overdue | today`)
  - `TODOIST_MAX_ITEMS` (example: `8`)
  - `TODOIST_CACHE_TTL_MIN` (example: `10`)

### 4) Local development (optional)

Copy `.env.example` to `.env` and set:
- `GEMINI_API_KEY=...` (or `GOOGLE_API_KEY=...`)
- `GEMINI_MODEL=gemini-2.5-flash` (optional)
- `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image` (optional, hero image)
- `TODOIST_API_TOKEN=...` (optional, Todoist tasks section)
- `TODOIST_FILTER="overdue | today"` (optional)
- `TODOIST_MAX_ITEMS=8` (optional)
- `TODOIST_CACHE_TTL_MIN=10` (optional)
- `EMAIL_RENDER_MODE=email-safe` (optional)
- `THEME_PROFILE=offwhite-slate` (optional)
- `EMAIL_HTML_BUDGET_BYTES=102400` (optional warning threshold)
- `EMAIL_USER=...`
- `EMAIL_PASS=...`
- `EMAIL_TO=...`

### 5) Run workflow

`Generate Morning Brief` now runs automatically on `main` pushes and also on schedule.
You can still run it manually from GitHub Actions (`workflow_dispatch`) when needed.

## Email QA Matrix (Visual Consistency)

When changing email design, validate the same generated `index.html` in:
- Apple Mail (iOS)
- Gmail app (iOS)
- Gmail app (Android)
- Outlook app (iOS)
- Outlook app (Android)
- Outlook desktop/web

Checkpoints:
- Header text/date spacing and off-white background consistency
- Card borders/padding and tag colors
- Weather icon image loads with fixed size (`40x40`)
- Finance pills and list readability
- Links and anchor tap behavior
- Plain-text fallback readability (non-HTML clients)
- Payload size warning does not exceed budget (`EMAIL_HTML_BUDGET_BYTES`, default `102400`)

## Contributors

- Fatih Üstün
- Claude (AI assistant)
- Codex (OpenAI coding assistant)
