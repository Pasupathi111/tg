"""Assignment readiness (dashboard): one row per active employee for a period.

Everything is derived from the stored documents, employees, timesheets, reviews and runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .engine import dec, period_bounds

STALL_HOURS = 48
EXCEPTION_TYPES = [
    ('missing_po', 'Missing or expired PO'),
    ('project_timesheet', 'Wrong project code / missing timesheet'),
    ('rate_approval', 'Rate discrepancy / missing approval'),
    ('invoicing_instruction', 'Unmatched / ambiguous / superseded instruction'),
]


def _doc_for(emp: dict, docs: List[dict], period: str) -> Optional[dict]:
    """Document that covers the employee; prefer one valid for the period."""
    cands = [d for d in docs if emp['id'] in (d.get('staff_ids') or [])]
    if not cands:
        cands = [d for d in docs if not d.get('staff_ids') and d.get('party') and d['party'] == emp.get('party')]
    if not cands:
        return None
    return next((d for d in cands if _po_state(d, period) == 'Active'), cands[0])


def _po_state(doc: Optional[dict], period: str) -> str:
    if not doc:
        return 'Missing'
    start, end = period_bounds(period)
    ins = doc.get('instructions') or {}
    if ins.get('valid_to') and ins['valid_to'] < start:
        return 'Expired'
    if ins.get('valid_from') and ins['valid_from'] > end:
        return 'Not started'
    return 'Active'


def _timesheet(ts: Optional[dict]) -> tuple:
    if not ts:
        return 'Missing', 'bad'
    sched = dec(ts.get('scheduled_days'))
    covered = dec(ts.get('worked_days')) + dec(ts.get('paid_leave_days')) + dec(ts.get('unpaid_leave_days'))
    gap = sched - covered
    if gap > 0:
        return f'Missing {gap.normalize():f} days', 'warn'
    return 'Complete', 'ok'


def _rate(emp: dict, doc: Optional[dict], reviews: List[dict]) -> tuple:
    basis = (emp.get('pay_basis') or 'monthly').lower()
    own = {'monthly': 'monthly_salary', 'hourly': 'hourly_rate', 'weekly': 'weekly_rate',
           'half_day': 'half_day_rate', 'daily': 'daily_rate'}[basis]
    if dec(emp.get(own)) <= 0:
        return 'Missing', 'bad'
    ins = (doc or {}).get('instructions') or {}
    if doc and ins.get('billing_basis') == 'rate_card' and not dec((ins.get('rates') or {}).get(basis)):
        return 'Pending approval', 'warn'
    short = emp['name'].split(' - ')[0]  # e.g. 'Officer C'
    if doc and any(
        r.get('category') == 'rate_approval'
        and r.get('status') != 'Resolved'
        and r.get('document_id') == doc['id']
        and short in (r.get('detail') or '')
        for r in reviews
    ):
        return 'Discrepancy', 'warn'
    return 'Approved', 'ok'


def _instruction(doc: Optional[dict], po: str) -> tuple:
    if not doc:
        return 'No PO', 'grey'
    conf = int(doc.get('confidence') or 0)
    if doc.get('status') == 'Needs confirmation' or conf < 80:
        return f'Ambiguous {conf}%', 'warn'
    return f'Matched {conf}%', 'ok'


def build_assignments(period: str, docs, employees, timesheets, reviews) -> List[dict]:
    ts_by = {t['employee_id']: t for t in timesheets if t.get('period') == period}
    rows = []
    for emp in employees:
        if emp.get('active') is False:
            continue
        doc = _doc_for(emp, docs, period)
        po = _po_state(doc, period)
        ts_label, ts_tone = _timesheet(ts_by.get(emp['id']))
        rate_label, rate_tone = _rate(emp, doc, reviews)
        ins_label, ins_tone = _instruction(doc, po)

        if po in ('Missing', 'Expired', 'Not started'):
            status = 'Blocked'
        elif ts_tone != 'ok' or rate_tone != 'ok' or ins_tone == 'warn':
            status = 'Needs confirmation' if (ins_tone == 'warn' and ts_tone == 'ok' and rate_tone == 'ok') else 'Not ready'
        else:
            status = 'Ready'
        rows.append(
            {
                'employee_id': emp['id'],
                'worker': emp['name'],
                'code': emp.get('code'),
                'party': emp.get('party'),
                'project_code': emp.get('project_code') or '—',
                'po_ref': (doc or {}).get('ref') or '—',
                'document_id': (doc or {}).get('id'),
                'timesheet': {'label': ts_label, 'tone': ts_tone},
                'po': {'label': po, 'tone': 'ok' if po == 'Active' else 'bad'},
                'rate': {'label': rate_label, 'tone': rate_tone},
                'instruction': {'label': ins_label, 'tone': ins_tone},
                'status': status,
                'group': 'Ready' if status == 'Ready' else ('Blocked' if status == 'Blocked' else 'Not ready'),
            }
        )
    return rows


def exceptions_by_type(assignments: List[dict]) -> List[dict]:
    """Exception counts for the period, derived from that period's assignment checks."""
    rules = {
        'missing_po': lambda a: a['po']['tone'] != 'ok',
        'project_timesheet': lambda a: a['timesheet']['tone'] != 'ok',
        'rate_approval': lambda a: a['rate']['tone'] != 'ok',
        'invoicing_instruction': lambda a: a['instruction']['tone'] in ('warn', 'grey'),
    }
    return [
        {'category': c, 'label': l, 'count': sum(1 for a in assignments if rules[c](a))}
        for c, l in EXCEPTION_TYPES
    ]


def pipeline(runs: List[dict], period: str) -> dict:
    now = datetime.now(timezone.utc)
    rs = [r for r in runs if r.get('period') == period]
    awaiting = [r for r in rs if r.get('status') == 'Awaiting validation']
    stalled = 0
    for r in awaiting:
        try:
            age = (now - datetime.fromisoformat(r.get('updated_at') or r.get('created_at'))).total_seconds() / 3600
        except Exception:
            continue
        if age > STALL_HOURS:
            stalled += 1
    return {
        'draft': sum(1 for r in rs if r.get('status') == 'Draft'),
        'awaiting': len(awaiting),
        'approved': sum(1 for r in rs if r.get('status') == 'Approved'),
        'stalled': stalled,
        'stall_hours': STALL_HOURS,
    }
