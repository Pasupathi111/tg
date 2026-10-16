# TG (renamed Open WebUI) + Billing Coworker

Folder: `TG\open-webui` (clone of open-webui/open-webui, shallow, v0.12.2). Spec: `TG-INVOICE-SPEC.md`.

## Run locally
1. Backend (port 8080, ~2 min to start): run `start-backend.bat` (uses `open-webui\.venv-tg`, data in `data-tg\`).
2. Frontend (port 5173): `cd open-webui` then `npm run dev -- --port 5173`.
3. Open http://localhost:5173/auth. The first account created in `data-tg` is admin
   (local dev admin: `admin@tg.local`, password in your own notes - change it).
4. Billing Coworker: http://localhost:5173/billing (also linked in the sidebar).

## What was built
- Billing Coworker UI (navy sidebar, orange accents) from the wireframe: Dashboard, Master Data (knowledge base upload of
  PO / quotation / contract + employees), Review Queue, Invoice Preparation (4 steps + chat panel), Ask Me, Settings.
- Backend `backend/open_webui/routers/tg_billing.py` + `utils/tg_billing/` (extractor, Decimal rule engine, JSON store).
  Tests: `backend/open_webui/test/tg_billing` (32 pass).
- Billing bases: cost_plus (comp + CPF + SDL + fee %) and rate_card (monthly / half-day / daily / weekly / hourly rates from the document).
- Sample document: `sample-docs/QTN-3050-AgencyE.txt`.
- Rename: UI strings, WEBUI_NAME default, favicon/logo/splash now "TG". Note Open WebUI's license restricts removing its branding
  for larger deployments; review `LICENSE` before any production use.

## Not done / known
- AI assistant is rule-based (no LLM calls); adjustments need confirmation and are audit-logged.
- Only static icons were replaced; some non-English translations and docs links still mention upstream project URLs.

## Server deploy (rt.dbizlab.com)
- Port **4060** (free at check time; nginx `rt.dbizlab.com` -> `localhost:4060`, SSL via Certbot).
- `cp .env.example .env`, fill `WEBUI_SECRET_KEY` / `OPENAI_API_KEY`, set `TG_PORT=4060`, `WEBUI_URL=https://rt.dbizlab.com`.
- Build frontend: `cd open-webui && npm ci --legacy-peer-deps && npm run build`; venv: `uv venv --python 3.11 .venv-tg && uv pip install -r backend/requirements.txt`.
- Run: `mkdir -p data-tg && ./start-backend.sh` (backend serves the built frontend on TG_PORT).
