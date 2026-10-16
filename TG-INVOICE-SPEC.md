# TG Billing Coworker — build spec (inside TG = renamed Open WebUI)

Source design: Figma-style wireframe "TG Singapore — Invoice Orchestration POV Wireframe"
(claude.ai artifact EiPNrt4YQA5Ruo99G9rRen). Screens: Login, Dashboard, Master Data, Review Queue,
Invoice Preparation (1 Sources & instructions, 2 Calculate, 3 Preview & validate, 4 Approve & download),
Ask Me, Settings. Product name in UI: "Billing Coworker — Powered by DBiz", company "APBA TG Human Resource Pte Ltd".

## Concept
User uploads PO / Quotation / Contract documents (knowledge base). System extracts billing instructions
(billing basis, rates: monthly / half-day / daily / weekly / hourly, management-fee %, GST %, period, invoice split,
mandatory references, validity dates). Employee master + timesheets are inputs. A DETERMINISTIC rule engine
calculates the invoice; the AI assistant only explains / proposes adjustments, every change needs confirmation and is
logged in an audit log. PO/Quotation, employee records, timesheets are never edited by the assistant.

## Visual style (replicate)
- Left sidebar 220px, navy `#2B3C50` (bg), white text, logo card (white rounded box with orange TG sunburst logo +
  "Billing Coworker" bold white + "Powered by DBiz" muted). Nav: Dashboard, Master Data, Review Queue,
  Invoice Preparation, Ask Me; bottom: Settings, Sign out. Active item: slightly lighter navy bg + 3px orange left border.
- Page bg `#F6F7F9`-ish near-white, cards white with 1px `#E3E7EC` border, radius 12px.
- Primary orange `#C8610F` (buttons, active step border `#E8892B`), orange light logo `#E8892B`,
  teal accent `#0E7C8F` for links / completed step number / "Pass"/"Received" pills (bg `#DDF1F5`),
  warning pill bg `#FCE9D8` text `#B4560A`, dark pill (Read-only / Ready) bg `#2B3C50` text white.
- Headings navy `#22344A`, body text `#33414F`, muted `#6B7785`. Font: Roboto/Inter-like sans; mono (Courier-like) for codes.
- Step tabs: 4 cards in a row (STEP 1..4), active = orange border + orange number circle, done = teal circle, pending = grey.
- Tables: header row grey `#F1F3F6` uppercase small; section rows (A · TIME WORKED …) grey bg uppercase label; right-aligned amounts;
  "Source" column with teal underlined links; adjusted rows light orange `#FDF1E6`.
- Right-hand "Billing Coworker" chat panel (width ~320px, slide-in) on Calculate step with context chips,
  numbered derivation steps, a confirmation card (orange border, "Needs your confirmation", FROM/TO table, reason input,
  "Apply change" orange / "Discard" outline), suggestion chips, input + Send button, disclaimer text.
- Invoice preview: white sheet, TG logo top-left, "TAX INVOICE" top-right, bill-to / references / billing period columns,
  grey "Billing instructions (from PO …)" box, officer table (Officer, Pay basis, Employment cost, Mgmt fee, Amount),
  Subtotal / GST 9% / Total SGD.
- Right column on Preview: "Validate" card (3 buttons: Amount correct · approve billing (orange), Calculation wrong · fix with
  Billing Coworker, Source data wrong · flag & email team), "Checks" card with pills.

## Calculation rules (Singapore, all editable in Settings)
Per employee per period:
- scheduled_days (working days), paid_days = worked + paid_leave, unpaid_leave days, OT hours.
- daily_rate = monthly_salary / scheduled_days. base_pay = daily_rate * paid_days (monthly basis).
- hourly basis: base = hourly_rate * hours; weekly basis: weekly_rate * weeks; half_day basis: half_day_rate * half_days; daily: daily_rate*days.
- OT pay = ot_hours * hourly_equivalent * ot_multiplier (default 1.5) where hourly_equivalent = monthly_salary*12/(52*44).
- allowances added; deductions = unpaid leave. gross = base + ot + allowances - deductions.
- Employer CPF = cpf_rate% (17% for age<=55, 0 for non-resident/foreign) * min(ordinary wages, OW ceiling 8000) ; SDL = 0.25% of gross (min 2, max 11.25);
  other contributions (foreign worker levy) from employee record.
- Billing basis "cost_plus": cost = gross + cpf + sdl + other; fee = fee_pct% * cost; subtotal = cost + fee; GST = gst_pct% of subtotal.
- Billing basis "rate_card" (contract/quotation job pricing): amount per employee = units * contracted rate
  (monthly rate, half-day rate, daily, hourly) taken from the document; fee 0 unless doc says; GST on subtotal.
- All money rounded to 2 dp (ROUND_HALF_UP via Decimal). Totals must equal sum of rounded lines.

## Storage
JSON-file store under `<DATA_DIR>/tg_billing/` (documents.json, employees.json, timesheets.json, runs.json, reviews.json,
audit.json, settings.json, uploads/). Seeded with dummy data on first access (4 POs/Quotations: PO 4500-0182 Agency A 3 staff
cost-plus, QTN-2231 Agency B 2 staff rate-card, PO 4500-0215 Agency D needs confirmation 62%, PO 4500-0201 Agency C expired; officers A monthly,
B hourly, G weekly, etc.; review exceptions EX-01..EX-08 as in the Review Queue screen).

## HTTP API — prefix `/api/v1/tg-billing`, all routes require a logged-in Open WebUI user (get_verified_user)
```
GET    /dashboard                      -> {kpis:{pos_ready,needs_confirmation,open_exceptions,runs_awaiting}, runs:[...], activity:[...]}
GET    /documents                      -> [Document]
POST   /documents  (multipart: file, doc_type?, party?)  -> Document   (extract text: pdf/docx/txt/csv/xlsx; parse instructions)
GET    /documents/{id}                 -> Document
PUT    /documents/{id}/instructions    -> Document   (user-corrected instructions; status -> Ready)
POST   /documents/{id}/confirm         -> Document
DELETE /documents/{id}
GET    /employees                      -> [Employee]       POST/PUT/DELETE /employees[/{id}]
GET    /timesheets?period=YYYY-MM      -> [Timesheet]      PUT /timesheets  (upsert one)
GET    /review-queue?category=         -> {counts:{all,missing_po,project_timesheet,rate_approval,invoicing_instruction}, items:[ReviewItem]}
POST   /review-queue/{id}/resolve      body {assignee?, note?, status}
POST   /calculate  body {document_id, period}  -> Run  (creates/overwrites draft run; includes per-employee lines, totals, checks)
GET    /runs  /runs/{id}
POST   /runs/{id}/adjustments  body {employee_id, field, new_value, reason, confirm:bool}
        confirm=false -> returns {proposal:{from,to,delta_total}}; confirm=true -> applies, recalculates, writes audit
POST   /runs/{id}/validate     body {outcome: "approve"|"fix"|"flag", note?}
GET    /runs/{id}/invoice              -> {invoice JSON}   GET /runs/{id}/invoice.html (printable)  GET /runs/{id}/billing-report.csv
POST   /runs/{id}/approve              -> Run (status Approved, invoice number assigned INV-YYYYMM-####)
POST   /ask  body {question, run_id?, document_id?} -> {answer, steps:[{n,title,text,source}], proposal?}
GET    /audit                          -> [AuditEntry]
GET    /settings  PUT /settings        -> {company, gst_pct, default_fee_pct, cpf:{rate_pct, ow_ceiling, ...}, sdl:{...}, ot_multiplier, ...}
POST   /reset-demo                     -> reseed
```
Document: {id, ref, doc_type, party, status:"Ready|Needs confirmation|Expired", confidence:0-100, source_filename, text_excerpt,
 instructions:{billing_basis:"cost_plus|rate_card", fee_pct, gst_pct, rates:{monthly,half_day,daily,weekly,hourly}, period_rule, invoice_split,
 mandatory_references:[], supporting_documents:[], tax_treatment, submission_channel, valid_from, valid_to, clause_refs:{}}, staff_ids:[], created_at}
Run: {id, document_id, period, status:"Draft|Awaiting validation|Approved", basis, lines:[{employee_id,name,pay_basis, sections:[{key:"A|B|C|D",title,rows:[{label,calc,amount,source,adjusted}]}], cost, fee, amount}],
 subtotal, gst_pct, gst, total, checks:[{label,result:"Pass|Match|Differs|Fail",value}], invoice_no, adjustments:[]}

## Frontend — SvelteKit routes (outside the `(app)` group so Open WebUI chat sidebar is NOT shown)
`src/routes/billing/+layout.svelte` (navy sidebar shell, auth guard: uses existing `user`/localStorage token, redirect to /auth),
`/billing` Dashboard, `/billing/master-data`, `/billing/review-queue`, `/billing/invoice` (4-step wizard w/ chat panel),
`/billing/ask`, `/billing/settings`. API client `src/lib/apis/tg-billing/index.ts`. Components under `src/lib/components/tg-billing/`.
Login screen: restyle existing `/auth` page to the TG login design (navy left panel with tagline, white right form, orange Sign in).
Also add a "Billing Coworker" entry in the standard Open WebUI sidebar linking to /billing.
