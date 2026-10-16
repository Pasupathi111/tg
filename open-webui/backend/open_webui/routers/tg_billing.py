"""TG Billing Coworker API (/api/v1/tg-billing). See TG-INVOICE-SPEC.md.

Calculation is deterministic (utils/tg_billing/engine.py). The assistant only explains and
proposes adjustments; every change needs confirmation and is written to the audit log.
"""

import copy
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict

from open_webui.env import DATA_DIR
from open_webui.utils.auth import get_verified_user
from open_webui.utils.tg_billing import engine, extractor, invoice, readiness
from open_webui.utils.tg_billing.ask import answer_question
from open_webui.utils.tg_billing.seed import seed as seed_fn
from open_webui.utils.tg_billing.store import Store

log = logging.getLogger(__name__)

router = APIRouter()

MAX_UPLOAD = 20 * 1024 * 1024
ALLOWED_EXT = ('.pdf', '.docx', '.txt', '.csv', '.xlsx', '.md')
PERIOD_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
PAY_BASES = ('monthly', 'hourly', 'weekly', 'half_day', 'daily')

_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(DATA_DIR / 'tg_billing', seed_fn)
    return _store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _actor(user) -> str:
    return getattr(user, 'email', None) or getattr(user, 'name', None) or 'user'


def _err(code: int, msg: str):
    raise HTTPException(status_code=code, detail=msg)


# ----------------------------------------------------------------------------- models
class InstructionsForm(BaseModel):
    model_config = ConfigDict(extra='allow')


class EmployeeForm(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: Optional[str] = None
    code: Optional[str] = None
    party: Optional[str] = None
    designation: Optional[str] = None
    pay_basis: Optional[str] = None
    age: Optional[int] = None
    residency: Optional[str] = None
    monthly_salary: Optional[float] = None
    hourly_rate: Optional[float] = None
    weekly_rate: Optional[float] = None
    half_day_rate: Optional[float] = None
    daily_rate: Optional[float] = None
    allowances: Optional[list] = None
    other_contributions: Optional[list] = None
    active: Optional[bool] = None


class TimesheetForm(BaseModel):
    employee_id: str
    period: str
    scheduled_days: Optional[float] = None
    worked_days: Optional[float] = None
    paid_leave_days: Optional[float] = None
    unpaid_leave_days: Optional[float] = None
    ot_hours: Optional[float] = None
    hours: Optional[float] = None
    weeks: Optional[float] = None
    half_days: Optional[float] = None
    deductions: Optional[float] = None
    status: Optional[str] = None


class ResolveForm(BaseModel):
    assignee: Optional[str] = None
    note: Optional[str] = None
    status: str


class CalculateForm(BaseModel):
    document_id: str
    period: str


class AdjustmentForm(BaseModel):
    employee_id: Optional[str] = None
    field: str
    new_value: Any
    reason: Optional[str] = None
    confirm: bool = False


class ValidateForm(BaseModel):
    outcome: str
    note: Optional[str] = None


class AskForm(BaseModel):
    question: str
    run_id: Optional[str] = None
    document_id: Optional[str] = None


class SettingsForm(BaseModel):
    model_config = ConfigDict(extra='allow')


# ----------------------------------------------------------------------------- helpers
def _doc_or_404(doc_id: str) -> dict:
    d = get_store().get('documents', doc_id)
    if not d:
        _err(404, 'Document not found')
    return d


def _run_or_404(run_id: str) -> dict:
    r = get_store().get('runs', run_id)
    if not r:
        _err(404, 'Run not found')
    return r


def _doc_staff(doc: dict) -> list:
    emps = get_store().all('employees')
    ids = doc.get('staff_ids') or []
    if ids:
        by_id = {e['id']: e for e in emps}
        return [by_id[i] for i in ids if i in by_id]
    return [e for e in emps if doc.get('party') and e.get('party') == doc.get('party') and e.get('active', True)]


def _compute(run: dict) -> dict:
    """Recompute run values from the document, master data and the run's overrides."""
    st = get_store()
    doc = _doc_or_404(run['document_id'])
    built = engine.build_run(doc, run['period'], _doc_staff(doc), st.all('timesheets'), st.settings(), run.get('overrides') or {})
    run.update(built)
    run['document_ref'] = doc.get('ref')
    run['party'] = doc.get('party')
    run['updated_at'] = _now()
    return run


def _run_summary(r: dict) -> dict:
    return {
        'id': r['id'],
        'document_id': r['document_id'],
        'document_ref': r.get('document_ref'),
        'party': r.get('party'),
        'period': r['period'],
        'status': r['status'],
        'basis': r.get('basis'),
        'subtotal': r.get('subtotal'),
        'gst': r.get('gst'),
        'total': r.get('total'),
        'invoice_no': r.get('invoice_no'),
        'updated_at': r.get('updated_at'),
        'staff': len(r.get('lines') or []),
        'approved_by': r.get('approved_by'),
        'approved_at': r.get('approved_at'),
        'flagged': (r.get('validation') or {}).get('outcome') == 'flag' and r['status'] != 'Approved',
    }


def _to_number(v: Any, field: str) -> float:
    try:
        n = float(str(v).replace(',', ''))
    except (ValueError, TypeError):
        _err(422, f'new_value for {field} must be a number')
    if n < 0 or n != n or n in (float('inf'),):
        _err(422, f'new_value for {field} must be a non-negative number')
    return n


def _current_value(run: dict, employee_id: str, field: str):
    st = get_store()
    ov = (run.get('overrides') or {})
    if field == 'fee_pct':
        if 'fee_pct' in ov.get('*', {}):
            return ov['*']['fee_pct']
        doc = _doc_or_404(run['document_id'])
        fp = (doc.get('instructions') or {}).get('fee_pct')
        return fp if fp is not None else st.settings().get('default_fee_pct')
    emp = st.get('employees', employee_id) or {}
    ts = next((t for t in st.all('timesheets') if t['employee_id'] == employee_id and t['period'] == run['period']), None)
    return engine.effective(emp, ts, ov.get(employee_id, {}), field)


def _propose(run: dict, employee_id: Optional[str], field: str, new_value: Any, reason: Optional[str]) -> dict:
    if field not in engine.ADJUSTABLE_FIELDS:
        _err(422, f'Field {field} cannot be adjusted. Allowed: {", ".join(engine.ADJUSTABLE_FIELDS)}')
    value = _to_number(new_value, field)
    if field == 'fee_pct':
        employee_id = '*'
        name = 'All officers'
    else:
        if not employee_id or not any(l['employee_id'] == employee_id for l in run['lines']):
            _err(404, 'employee_id is not part of this run')
        name = next(l['name'] for l in run['lines'] if l['employee_id'] == employee_id)
    frm = _current_value(run, employee_id, field)
    trial = copy.deepcopy(run)
    trial.setdefault('overrides', {}).setdefault(employee_id, {})[field] = value
    _compute(trial)
    return {
        'employee_id': employee_id,
        'name': name,
        'field': field,
        'from': frm,
        'to': value,
        'reason': reason,
        'old_total': run['total'],
        'new_total': trial['total'],
        'delta_total': float(engine.q(engine.dec(trial['total']) - engine.dec(run['total']))),
    }


def _invoice_no(period: str, runs: list) -> str:
    prefix = f'INV-{period.replace("-", "")}-'
    n = 0
    for r in runs:
        no = r.get('invoice_no') or ''
        if no.startswith(prefix):
            n = max(n, int(no[len(prefix):] or 0))
    return f'{prefix}{n + 1:04d}'


# ----------------------------------------------------------------------------- dashboard
@router.get('/dashboard')
def dashboard(period: Optional[str] = Query(None), user=Depends(get_verified_user)):
    st = get_store()
    docs, runs, reviews = st.all('documents'), st.all('runs'), st.all('reviews')
    audit = st.all('audit')
    if period and not PERIOD_RE.match(period):
        _err(422, 'period must be YYYY-MM')
    period = period or datetime.now(timezone.utc).strftime('%Y-%m')
    assignments = readiness.build_assignments(period, docs, st.all('employees'), st.all('timesheets'), reviews)
    exceptions = readiness.exceptions_by_type(assignments)
    p_runs = [r for r in runs if r['period'] == period]
    run_ids = {r['id'] for r in p_runs}
    valid_docs = {a['document_id'] for a in assignments if a['po']['tone'] == 'ok' and a['document_id']}
    p_docs = [d for d in docs if d['id'] in valid_docs]
    return {
        'period': period,
        'assignments': assignments,
        'exceptions': exceptions,
        'pipeline': readiness.pipeline(runs, period),
        'kpis': {
            'pos_ready': sum(1 for d in p_docs if d['status'] == 'Ready'),
            'needs_confirmation': sum(1 for d in p_docs if d['status'] == 'Needs confirmation'),
            'open_exceptions': sum(e['count'] for e in exceptions),
            'runs_awaiting': sum(1 for r in p_runs if r['status'] in ('Draft', 'Awaiting validation')),
        },
        'runs': [_run_summary(r) for r in sorted(p_runs, key=lambda x: x.get('updated_at') or '', reverse=True)],
        'activity': list(reversed([a for a in audit if a.get('run_id') in run_ids][-15:])),
    }


# ----------------------------------------------------------------------------- documents
@router.get('/documents')
def list_documents(user=Depends(get_verified_user)):
    return get_store().all('documents')


@router.post('/documents')
def upload_document(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    party: Optional[str] = Form(None),
    user=Depends(get_verified_user),
):
    st = get_store()
    fname = file.filename or 'upload.txt'
    if not fname.lower().endswith(ALLOWED_EXT):
        _err(415, f'Unsupported file type. Allowed: {", ".join(ALLOWED_EXT)}')
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        _err(413, 'File too large (max 20 MB)')
    if not data:
        _err(422, 'File is empty')
    try:
        text = extractor.extract_text(fname, data)
    except Exception as e:
        log.warning('tg_billing extract failed: %s', e)
        _err(422, 'Could not read text from this file')
    if not text.strip():
        _err(422, 'No text could be extracted from this file')

    emps = st.all('employees')
    parsed = extractor.parse_instructions(text, fname, emps)
    ref = parsed['ref'] or re.sub(r'\.[^.]+$', '', fname)
    same = next((d for d in st.all('documents') if (d.get('ref') or '').lower() == ref.lower()), None)
    doc_id = same['id'] if same else f'DOC-{uuid.uuid4().hex[:6].upper()}'
    p = (party or parsed['party'] or '').strip() or None
    staff = parsed['staff_ids']
    if not staff and p:
        staff = [e['id'] for e in emps if e.get('party') == p and e.get('active', True)]
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', fname)
    (st.uploads / f'{doc_id}_{safe}').write_bytes(data)
    (st.uploads / f'{doc_id}.txt').write_text(text, encoding='utf-8')
    doc = {
        'id': doc_id,
        'ref': ref,
        'doc_type': (doc_type or parsed['doc_type']),
        'party': p,
        'status': extractor.status_for(parsed['confidence'], parsed['instructions']),
        'confidence': parsed['confidence'],
        'source_filename': fname,
        'text_excerpt': text[:1500],
        'instructions': parsed['instructions'],
        'staff_ids': (same.get('staff_ids') if same and same.get('staff_ids') else staff),
        'created_at': (same or {}).get('created_at') or _now(),
    }
    if same:
        doc['updated_at'] = _now()
    st.save_item('documents', doc)
    st.audit(
        _actor(user),
        'document.upload',
        f'{"Re-uploaded" if same else "Uploaded"} {fname} as {doc["ref"]} (confidence {doc["confidence"]}%)',
        document_id=doc_id,
    )
    return {**doc, 'replaced': bool(same)}


@router.get('/documents/{doc_id}')
def get_document(doc_id: str, user=Depends(get_verified_user)):
    return _doc_or_404(doc_id)


@router.put('/documents/{doc_id}/instructions')
def update_instructions(doc_id: str, form: dict, user=Depends(get_verified_user)):
    """Accepts either the instructions object itself or {instructions: {...}, ref?, party?, doc_type?}."""
    st = get_store()
    doc = _doc_or_404(doc_id)
    body = form.get('instructions') if isinstance(form.get('instructions'), dict) else form
    allowed = set(doc['instructions'].keys()) | {'billing_basis'}
    if body.get('billing_basis') not in (None, 'cost_plus', 'rate_card'):
        _err(422, 'billing_basis must be cost_plus or rate_card')
    for k in ('fee_pct', 'gst_pct'):
        if body.get(k) not in (None, ''):
            n = _to_number(body[k], k)
            if n > 100:
                _err(422, f'{k} must be between 0 and 100')
            body[k] = n
    changes = []
    for k, v in body.items():
        if k not in allowed:
            continue
        if k == 'rates' and isinstance(v, dict):
            for rk, rv in v.items():
                if rk in doc['instructions']['rates']:
                    doc['instructions']['rates'][rk] = _to_number(rv, rk) if rv not in (None, '') else None
        else:
            doc['instructions'][k] = v
        changes.append(k)
    for k in ('ref', 'party', 'doc_type'):
        if isinstance(form.get(k), str) and form[k].strip():
            doc[k] = form[k].strip()
    if isinstance(form.get('staff_ids'), list):
        doc['staff_ids'] = form['staff_ids']
    doc['status'] = extractor.status_for(100, doc['instructions']) if (doc['instructions'].get('valid_to') or '9999') < _now()[:10] else 'Ready'
    st.save_item('documents', doc)
    st.audit(_actor(user), 'document.instructions', f'Corrected instructions on {doc["ref"]}: {", ".join(changes) or "none"}', document_id=doc_id)
    return doc


@router.post('/documents/{doc_id}/confirm')
def confirm_document(doc_id: str, user=Depends(get_verified_user)):
    st = get_store()
    doc = _doc_or_404(doc_id)
    expired = (doc['instructions'].get('valid_to') or '9999') < _now()[:10]
    doc['status'] = 'Expired' if expired else 'Ready'
    st.save_item('documents', doc)
    st.audit(_actor(user), 'document.confirm', f'Confirmed instructions of {doc["ref"]}', document_id=doc_id)
    return doc


@router.delete('/documents/{doc_id}')
def delete_document(doc_id: str, user=Depends(get_verified_user)):
    st = get_store()
    doc = _doc_or_404(doc_id)
    st.delete_item('documents', doc_id)
    for f in st.uploads.glob(f'{doc_id}*'):
        f.unlink(missing_ok=True)
    st.audit(_actor(user), 'document.delete', f'Deleted {doc["ref"]}', document_id=doc_id)
    return {'ok': True, 'id': doc_id}


# ----------------------------------------------------------------------------- employees
def _clean_employee(base: dict, form: EmployeeForm) -> dict:
    data = form.model_dump(exclude_unset=True)
    base.update({k: v for k, v in data.items() if v is not None or k in ('party', 'designation')})
    if base.get('pay_basis') not in PAY_BASES:
        _err(422, f'pay_basis must be one of {", ".join(PAY_BASES)}')
    if not (base.get('name') or '').strip():
        _err(422, 'name is required')
    if base.get('residency') not in ('citizen', 'pr', 'foreign'):
        base['residency'] = 'citizen'
    for k in ('monthly_salary', 'hourly_rate', 'weekly_rate', 'half_day_rate', 'daily_rate'):
        if float(base.get(k) or 0) < 0:
            _err(422, f'{k} cannot be negative')
        base[k] = float(base.get(k) or 0)
    base.setdefault('allowances', [])
    base.setdefault('other_contributions', [])
    base.setdefault('active', True)
    base.setdefault('age', 30)
    return base


@router.get('/employees')
def list_employees(user=Depends(get_verified_user)):
    return get_store().all('employees')


@router.post('/employees')
def create_employee(form: EmployeeForm, user=Depends(get_verified_user)):
    st = get_store()
    emp = _clean_employee({'id': f'EMP-{uuid.uuid4().hex[:6].upper()}', 'pay_basis': 'monthly'}, form)
    st.save_item('employees', emp)
    st.audit(_actor(user), 'employee.create', f'Created employee {emp["name"]}', employee_id=emp['id'])
    return emp


@router.put('/employees/{emp_id}')
def update_employee(emp_id: str, form: EmployeeForm, user=Depends(get_verified_user)):
    st = get_store()
    emp = st.get('employees', emp_id)
    if not emp:
        _err(404, 'Employee not found')
    emp = _clean_employee(emp, form)
    st.save_item('employees', emp)
    st.audit(_actor(user), 'employee.update', f'Updated employee {emp["name"]}', employee_id=emp_id)
    return emp


@router.delete('/employees/{emp_id}')
def delete_employee(emp_id: str, user=Depends(get_verified_user)):
    st = get_store()
    emp = st.get('employees', emp_id)
    if not emp:
        _err(404, 'Employee not found')
    st.delete_item('employees', emp_id)
    st.audit(_actor(user), 'employee.delete', f'Deleted employee {emp["name"]}', employee_id=emp_id)
    return {'ok': True, 'id': emp_id}


# ----------------------------------------------------------------------------- timesheets
@router.get('/timesheets')
def list_timesheets(period: Optional[str] = Query(None), user=Depends(get_verified_user)):
    if period and not PERIOD_RE.match(period):
        _err(422, 'period must be YYYY-MM')
    return [t for t in get_store().all('timesheets') if not period or t['period'] == period]


@router.put('/timesheets')
def upsert_timesheet(form: TimesheetForm, user=Depends(get_verified_user)):
    st = get_store()
    if not PERIOD_RE.match(form.period):
        _err(422, 'period must be YYYY-MM')
    if not st.get('employees', form.employee_id):
        _err(404, 'Employee not found')
    tid = f'TS-{form.employee_id}-{form.period}'
    ts = st.get('timesheets', tid) or {
        'id': tid,
        'employee_id': form.employee_id,
        'period': form.period,
        'scheduled_days': 0,
        'worked_days': 0,
        'paid_leave_days': 0,
        'unpaid_leave_days': 0,
        'ot_hours': 0,
        'deductions': 0,
        'status': 'Received',
    }
    for k, v in form.model_dump(exclude_unset=True).items():
        if k in ('employee_id', 'period') or v is None:
            continue
        if k != 'status' and v < 0:
            _err(422, f'{k} cannot be negative')
        ts[k] = v
    st.save_item('timesheets', ts)
    st.audit(_actor(user), 'timesheet.upsert', f'Timesheet {form.employee_id} {form.period} saved', employee_id=form.employee_id)
    return ts


@router.delete('/timesheets/{ts_id}')
def delete_timesheet(ts_id: str, user=Depends(get_verified_user)):
    st = get_store()
    if not st.delete_item('timesheets', ts_id):
        _err(404, 'Timesheet not found')
    st.audit(_actor(user), 'timesheet.delete', f'Timesheet {ts_id} deleted')
    return {'ok': True}


# ----------------------------------------------------------------------------- review queue
CATEGORIES = ('missing_po', 'project_timesheet', 'rate_approval', 'invoicing_instruction')


REVIEW_DEFAULTS = {
    'missing_po': (
        'Every timesheet must map to a PO / quotation that is valid for the billing period.',
        'Upload the renewed PO or quotation in Master Data and link the staff to it, or correct the timesheet period if it is wrong.',
    ),
    'project_timesheet': (
        'An approved timesheet must cover all scheduled days for every assigned officer each period.',
        "Add or correct the officer's timesheet in Master Data > Timesheets, then recalculate the invoice.",
    ),
    'rate_approval': (
        'The billing rate must exist in the PO / quotation and match the approved rate.',
        'Get the rate approved by the customer, then update the rate card (Edit instructions) or the employee rate.',
    ),
    'invoicing_instruction': (
        'Invoicing instructions (fee basis, GST, split, validity) must be unambiguous with confidence of 80% or more.',
        'Open the document, review the extracted instructions, correct them with Edit instructions and confirm.',
    ),
}


def _enrich_review(item: dict) -> dict:
    rule, sugg = REVIEW_DEFAULTS.get(item.get('category'), (None, None))
    out = dict(item)
    out.setdefault('rule', None)
    out['rule'] = item.get('rule') or rule
    out['suggestion'] = item.get('suggestion') or sugg
    ev = item.get('evidence')
    if not ev:
        ev = [x for x in (item.get('detail'), f'Document: {item["document_id"]}' if item.get('document_id') else None) if x]
    out['evidence'] = ev
    out['summary'] = item.get('summary') or item.get('detail')
    return out


@router.get('/review-queue')
def review_queue(category: Optional[str] = Query(None), user=Depends(get_verified_user)):
    items = [_enrich_review(i) for i in get_store().all('reviews')]
    open_items = [i for i in items if i.get('status') != 'Resolved']
    counts = {'all': len(open_items), **{c: sum(1 for i in open_items if i['category'] == c) for c in CATEGORIES}}
    if category and category != 'all':
        if category not in CATEGORIES:
            _err(422, f'category must be one of {", ".join(CATEGORIES)}')
        items = [i for i in items if i['category'] == category]
    return {'counts': counts, 'items': items}


class ReviewForm(BaseModel):
    category: str
    title: str
    party: Optional[str] = None
    detail: Optional[str] = None
    document_id: Optional[str] = None


@router.post('/review-queue')
def create_review(form: ReviewForm, user=Depends(get_verified_user)):
    st = get_store()
    if form.category not in CATEGORIES:
        _err(422, f'category must be one of {", ".join(CATEGORIES)}')
    if not form.title.strip():
        _err(422, 'title is required')
    reviews = st.all('reviews')
    n = max([int(r['id'].split('-')[1]) for r in reviews if re.fullmatch(r'EX-\d+', r['id'])] + [0]) + 1
    item = {
        'id': f'EX-{n:02d}',
        'category': form.category,
        'title': form.title.strip(),
        'party': form.party,
        'detail': form.detail,
        'document_id': form.document_id,
        'status': 'Open',
        'assignee': None,
        'note': None,
        'created_at': _now(),
    }
    st.save_item('reviews', item)
    st.audit(_actor(user), 'review.create', f'{item["id"]} created: {item["title"]}')
    return item


class ReviewEditForm(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    party: Optional[str] = None
    detail: Optional[str] = None
    document_id: Optional[str] = None
    rule: Optional[str] = None
    suggestion: Optional[str] = None
    evidence: Optional[list] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    note: Optional[str] = None


@router.put('/review-queue/{item_id}')
def edit_review(item_id: str, form: ReviewEditForm, user=Depends(get_verified_user)):
    st = get_store()
    item = st.get('reviews', item_id)
    if not item:
        _err(404, 'Item not found')
    data = form.model_dump(exclude_unset=True)
    if 'category' in data and data['category'] not in CATEGORIES:
        _err(422, f'category must be one of {", ".join(CATEGORIES)}')
    if 'title' in data and not (data['title'] or '').strip():
        _err(422, 'title is required')
    if data.get('status') not in (None, 'Open', 'Assigned', 'Resolved'):
        _err(422, 'status must be Open, Assigned or Resolved')
    item.update({k: v for k, v in data.items() if v is not None or k in ('party', 'detail', 'document_id', 'assignee', 'note')})
    item['updated_at'] = _now()
    st.save_item('reviews', item)
    st.audit(_actor(user), 'review.edit', f'{item_id} edited: {", ".join(data) or "no changes"}', review_id=item_id)
    return _enrich_review(item)


@router.delete('/review-queue/{item_id}')
def delete_review(item_id: str, user=Depends(get_verified_user)):
    st = get_store()
    if not st.delete_item('reviews', item_id):
        _err(404, 'Item not found')
    st.audit(_actor(user), 'review.delete', f'{item_id} deleted')
    return {'ok': True}


@router.post('/review-queue/{item_id}/resolve')
def resolve_review(item_id: str, form: ResolveForm, user=Depends(get_verified_user)):
    st = get_store()
    item = st.get('reviews', item_id)
    if not item:
        _err(404, 'Review item not found')
    if not form.status.strip():
        _err(422, 'status is required')
    item['status'] = form.status.strip()
    if form.assignee is not None:
        item['assignee'] = form.assignee
    if form.note is not None:
        item['note'] = form.note
    item['updated_at'] = _now()
    st.save_item('reviews', item)
    st.audit(_actor(user), 'review.update', f'{item_id} -> {item["status"]}' + (f' ({form.note})' if form.note else ''), review_id=item_id)
    return item


# ----------------------------------------------------------------------------- runs
@router.post('/calculate')
def calculate(form: CalculateForm, user=Depends(get_verified_user)):
    st = get_store()
    if not PERIOD_RE.match(form.period):
        _err(422, 'period must be YYYY-MM')
    doc = _doc_or_404(form.document_id)
    if not _doc_staff(doc):
        _err(422, 'No staff are linked to this document')
    existing = next((r for r in st.all('runs') if r['document_id'] == form.document_id and r['period'] == form.period), None)
    if existing and existing['status'] == 'Approved':
        _err(409, 'An approved run already exists for this document and period')
    inv_no = _invoice_no(form.period, st.all('runs')) if not existing else None
    run = existing or {
        'id': inv_no,
        'document_id': form.document_id,
        'period': form.period,
        'invoice_no': inv_no,
        'adjustments': [],
        'created_at': _now(),
        'created_by': _actor(user),
    }
    run['status'] = 'Draft'
    run['overrides'] = {}
    run['adjustments'] = []
    run['validation'] = None
    _compute(run)
    st.save_item('runs', run)
    st.audit(_actor(user), 'run.calculate', f'Calculated {doc["ref"]} for {form.period}: total S${run["total"]:,.2f}', run_id=run['id'])
    return run


@router.get('/runs')
def list_runs(user=Depends(get_verified_user)):
    return get_store().all('runs')


@router.get('/runs/{run_id}')
def get_run(run_id: str, user=Depends(get_verified_user)):
    return _run_or_404(run_id)


@router.delete('/runs/{run_id}')
def delete_run(run_id: str, user=Depends(get_verified_user)):
    st = get_store()
    run = _run_or_404(run_id)
    if run['status'] == 'Approved':
        _err(409, 'Approved invoices cannot be deleted')
    st.delete_item('runs', run_id)
    st.audit(_actor(user), 'run.delete', f'Draft invoice {run.get("invoice_no") or run_id} deleted', run_id=run_id)
    return {'ok': True}


@router.post('/runs/{run_id}/adjustments')
def adjust_run(run_id: str, form: AdjustmentForm, user=Depends(get_verified_user)):
    st = get_store()
    run = _run_or_404(run_id)
    if run['status'] == 'Approved':
        _err(409, 'Run is approved and locked')
    proposal = _propose(run, form.employee_id, form.field, form.new_value, form.reason)
    if not form.confirm:
        return {'proposal': proposal}
    if not (form.reason or '').strip():
        _err(422, 'A reason is required to apply a change')
    run.setdefault('overrides', {}).setdefault(proposal['employee_id'], {})[form.field] = proposal['to']
    _compute(run)
    adj = {
        'id': f'ADJ-{len(run.get("adjustments", [])) + 1:03d}',
        'ts': _now(),
        'actor': _actor(user),
        'employee_id': proposal['employee_id'],
        'name': proposal['name'],
        'field': form.field,
        'from': proposal['from'],
        'to': proposal['to'],
        'reason': form.reason.strip(),
        'delta_total': proposal['delta_total'],
    }
    run.setdefault('adjustments', []).append(adj)
    if run['status'] == 'Awaiting validation':
        run['status'] = 'Draft'
        run['validation'] = None
    st.save_item('runs', run)
    st.audit(
        _actor(user),
        'run.adjust',
        f'{proposal["name"]}: {form.field} {proposal["from"]} -> {proposal["to"]} ({adj["reason"]}); total change S${proposal["delta_total"]:,.2f}',
        run_id=run_id,
    )
    out = dict(run)
    out['applied'] = adj
    return out


@router.post('/runs/{run_id}/validate')
def validate_run(run_id: str, form: ValidateForm, user=Depends(get_verified_user)):
    st = get_store()
    run = _run_or_404(run_id)
    if form.outcome not in ('approve', 'fix', 'flag'):
        _err(422, 'outcome must be approve, fix or flag')
    if run['status'] == 'Approved':
        _err(409, 'Run is already approved')
    run['validation'] = {'outcome': form.outcome, 'note': form.note, 'by': _actor(user), 'ts': _now()}
    if form.outcome == 'fix':
        run['status'] = 'Draft'
    else:
        run['status'] = 'Awaiting validation'
    if form.outcome == 'flag':
        reviews = st.all('reviews')
        n = max([int(r['id'].split('-')[1]) for r in reviews if re.fullmatch(r'EX-\d+', r['id'])] + [0]) + 1
        st.save_item(
            'reviews',
            {
                'id': f'EX-{n:02d}',
                'category': 'project_timesheet',
                'title': f'Source data flagged on run {run_id}',
                'party': run.get('party'),
                'detail': form.note or 'Flagged during invoice validation',
                'document_id': run['document_id'],
                'status': 'Open',
                'assignee': None,
                'note': None,
                'created_at': _now(),
            },
        )
    st.save_item('runs', run)
    st.audit(_actor(user), 'run.validate', f'{run_id}: {form.outcome}' + (f' ({form.note})' if form.note else ''), run_id=run_id)
    return run


def _invoice_for(run: dict) -> dict:
    st = get_store()
    return invoice.build_invoice(run, st.get('documents', run['document_id']), st.settings())


@router.get('/runs/{run_id}/invoice')
def run_invoice(run_id: str, user=Depends(get_verified_user)):
    return _invoice_for(_run_or_404(run_id))


@router.get('/runs/{run_id}/invoice.html', response_class=HTMLResponse)
def run_invoice_html(run_id: str, user=Depends(get_verified_user)):
    return HTMLResponse(invoice.render_html(_invoice_for(_run_or_404(run_id))))


@router.get('/runs/{run_id}/billing-report.csv')
def run_csv(run_id: str, user=Depends(get_verified_user)):
    run = _run_or_404(run_id)
    body = invoice.render_csv(run, _invoice_for(run))
    return Response(
        body,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="billing-report-{run["period"]}-{run_id}.csv"'},
    )


@router.post('/runs/{run_id}/approve')
def approve_run(run_id: str, user=Depends(get_verified_user)):
    st = get_store()
    with st.lock():
        run = _run_or_404(run_id)
        if run['status'] == 'Approved':
            return run
        failing = [c['label'] for c in run.get('checks', []) if c['result'] == 'Fail']
        if failing:
            _err(422, 'Cannot approve while checks fail: ' + ', '.join(failing))
        run['status'] = 'Approved'
        run['invoice_no'] = run.get('invoice_no') or _invoice_no(run['period'], st.all('runs'))
        run['approved_at'] = _now()
        run['approved_by'] = _actor(user)
        run['updated_at'] = _now()
        st.save_item('runs', run)
        st.audit(_actor(user), 'run.approve', f'{run_id} approved as {run["invoice_no"]} (total S${run["total"]:,.2f})', run_id=run_id)
    return run


# ----------------------------------------------------------------------------- ask / audit / settings
@router.post('/ask')
def ask(form: AskForm, user=Depends(get_verified_user)):
    if not form.question.strip():
        _err(422, 'question is required')
    st = get_store()
    run = st.get('runs', form.run_id) if form.run_id else None
    if form.run_id and not run:
        _err(404, 'Run not found')
    doc = st.get('documents', form.document_id) if form.document_id else None
    if form.document_id and not doc:
        _err(404, 'Document not found')
    if run and not doc:
        doc = st.get('documents', run['document_id'])
    res = answer_question(form.question, run, doc)
    req = res.pop('proposal_request', None)
    if req and run:
        try:
            res['proposal'] = _propose(run, req['employee_id'], req['field'], req['new_value'], 'Requested via Ask')
            res['answer'] = (
                f'Proposed change: {res["proposal"]["name"]} {res["proposal"]["field"]} from {res["proposal"]["from"]} '
                f'to {res["proposal"]["to"]} (total change S${res["proposal"]["delta_total"]:,.2f}). Nothing is applied until you confirm.'
            )
        except HTTPException as e:
            res['answer'] = f'I could not propose that change: {e.detail}'
    res.setdefault('steps', [])
    return res


@router.get('/audit')
def audit_log(user=Depends(get_verified_user)):
    return list(reversed(get_store().all('audit')))


@router.get('/settings')
def get_settings(user=Depends(get_verified_user)):
    return get_store().settings()


@router.put('/settings')
def put_settings(form: dict, user=Depends(get_verified_user)):
    st = get_store()
    for k in ('gst_pct', 'default_fee_pct', 'ot_multiplier'):
        if k in form:
            n = _to_number(form[k], k)
            if k != 'ot_multiplier' and n > 100:
                _err(422, f'{k} must be between 0 and 100')
            form[k] = n
    cpf = form.get('cpf')
    if isinstance(cpf, dict):
        for k in ('rate_pct', 'ow_ceiling', 'senior_rate_pct'):
            if k in cpf:
                cpf[k] = _to_number(cpf[k], f'cpf.{k}')
    sdl = form.get('sdl')
    if isinstance(sdl, dict):
        for k in ('rate_pct', 'min', 'max'):
            if k in sdl:
                sdl[k] = _to_number(sdl[k], f'sdl.{k}')
        merged = {**st.settings()['sdl'], **sdl}
        if merged['min'] > merged['max']:
            _err(422, 'sdl.min cannot exceed sdl.max')
    out = st.save_settings(form)
    st.audit(_actor(user), 'settings.update', f'Settings updated: {", ".join(form.keys())}')
    return out


@router.post('/reset-demo')
def reset_demo(user=Depends(get_verified_user)):
    get_store().reset()
    return {'ok': True}
