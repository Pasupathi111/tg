"""Rule-based 'Ask Me' answers. Explains steps from a run's rows with sources; never edits data.
A change request ("set OT hours for Officer A to 8") returns a `proposal_request`, which the router
turns into a confirmable proposal."""

from __future__ import annotations

import re
from typing import Optional

FIELD_ALIASES = [
    (r'ot hours|overtime hours|overtime|\bot\b', 'ot_hours'),
    (r'unpaid leave( days)?', 'unpaid_leave_days'),
    (r'paid leave( days)?', 'paid_leave_days'),
    (r'worked days|days worked|working days worked', 'worked_days'),
    (r'scheduled days', 'scheduled_days'),
    (r'half[- ]?days?', 'half_days'),
    (r'weeks', 'weeks'),
    (r'hours', 'hours'),
    (r'monthly salary|salary', 'monthly_salary'),
    (r'hourly rate', 'hourly_rate'),
    (r'weekly rate', 'weekly_rate'),
    (r'daily rate', 'daily_rate'),
    (r'fee( %| percent| pct)?|management fee', 'fee_pct'),
]

TOPICS = {
    'cpf': (['cpf'], 'Employer contributions'),
    'sdl': (['sdl', 'skills development'], 'Employer contributions'),
    'fee': (['fee', 'margin', 'markup', 'mark-up'], 'Management fee'),
    'gst': (['gst', 'tax'], None),
    'ot': (['overtime', ' ot ', 'ot?'], 'Overtime'),
    'base': (['base', 'salary', 'basic', 'pay'], 'Base pay'),
}


def _find_line(question: str, run: dict) -> Optional[dict]:
    q = question.lower()
    best = None
    for l in run['lines']:
        name = (l['name'] or '').lower()
        tokens = [t for t in re.split(r'[\s\-]+', name) if len(t) >= 2]
        # "officer a" style code or any distinctive name token
        if name and name in q:
            return l
        m = re.search(r'officer\s+([a-z])\b', name)
        if m and re.search(r'officer\s+' + m.group(1) + r'\b', q):
            best = best or l
        for t in tokens:
            if t not in ('officer',) and len(t) > 2 and re.search(r'\b' + re.escape(t) + r'\b', q):
                best = best or l
    if best:
        return best
    if len(run['lines']) == 1:
        return run['lines'][0]
    return None


def _line_steps(line: dict, topic: Optional[str]) -> list:
    steps = []
    n = 1
    for s in line['sections']:
        for r in s['rows']:
            if topic:
                kws, label = TOPICS[topic]
                hay = (r['label'] + ' ' + s['title']).lower()
                if not (any(k.strip(' ?') in hay for k in kws)):
                    continue
            steps.append(
                {
                    'n': n,
                    'title': r['label'] + (' (adjusted)' if r.get('adjusted') else ''),
                    'text': f'{r["calc"]} = S${r["amount"]:,.2f}',
                    'source': r['source'],
                }
            )
            n += 1
    if not topic:
        steps.append({'n': n, 'title': 'Cost', 'text': f'Sum of sections A-C = S${line["cost"]:,.2f}', 'source': 'Rule engine'})
        steps.append({'n': n + 1, 'title': 'Line amount', 'text': f'Cost S${line["cost"]:,.2f} + fee S${line["fee"]:,.2f} = S${line["amount"]:,.2f}', 'source': 'Rule engine'})
    return steps


def parse_change(question: str, run: dict) -> Optional[dict]:
    m = re.search(
        r'\b(?:change|set|update|make|adjust|correct)\b\s+(?:the\s+)?(.+?)\s+(?:for\s+(.+?)\s+)?(?:to|=|as)\s+(-?\d+(?:\.\d+)?)\b',
        question,
        re.I,
    )
    if not m:
        return None
    what, who, val = m.group(1), m.group(2), m.group(3)
    field = None
    for pat, f in FIELD_ALIASES:
        if re.search(pat, what, re.I):
            field = f
            break
    if not field:
        return None
    line = None
    if field == 'fee_pct':
        return {'employee_id': '*', 'field': field, 'new_value': val}
    line = _find_line(who or question, run)
    if not line:
        return None
    return {'employee_id': line['employee_id'], 'field': field, 'new_value': val}


def answer_question(question: str, run: Optional[dict], doc: Optional[dict]) -> dict:
    ql = f' {question.lower()} '
    if run:
        change = parse_change(question, run)
        if change:
            return {
                'answer': 'I can propose that change. It will not be applied until you confirm it, and the source records stay untouched.',
                'steps': [],
                'proposal_request': change,
            }
        line = _find_line(question, run)
        topic = None
        for t, (kws, _) in TOPICS.items():
            if any(k in ql for k in kws):
                topic = t
                break
        if re.search(r'\btotal\b|\binvoice\b|subtotal|how much', ql) and not line and topic != 'gst':
            steps = [
                {'n': i + 1, 'title': l['name'], 'text': f'Cost S${l["cost"]:,.2f} + fee S${l["fee"]:,.2f} = S${l["amount"]:,.2f}', 'source': f'Invoice {run.get("invoice_no") or run["id"]}'}
                for i, l in enumerate(run['lines'])
            ]
            k = len(steps)
            steps.append({'n': k + 1, 'title': 'Subtotal', 'text': f'Sum of line amounts = S${run["subtotal"]:,.2f}', 'source': 'Rule engine'})
            steps.append({'n': k + 2, 'title': f'GST {run["gst_pct"]:g}%', 'text': f'S${run["subtotal"]:,.2f} x {run["gst_pct"]:g}% = S${run["gst"]:,.2f}', 'source': 'PO billing instructions'})
            steps.append({'n': k + 3, 'title': 'Total', 'text': f'S${run["subtotal"]:,.2f} + S${run["gst"]:,.2f} = S${run["total"]:,.2f}', 'source': 'Rule engine'})
            return {'answer': f'The invoice total for {run["period"]} is S${run["total"]:,.2f} (subtotal S${run["subtotal"]:,.2f} + GST S${run["gst"]:,.2f}).', 'steps': steps}
        if topic == 'gst':
            return {
                'answer': f'GST is {run["gst_pct"]:g}% of the subtotal: S${run["subtotal"]:,.2f} x {run["gst_pct"]:g}% = S${run["gst"]:,.2f}.',
                'steps': [{'n': 1, 'title': 'GST', 'text': f'S${run["subtotal"]:,.2f} x {run["gst_pct"]:g}% = S${run["gst"]:,.2f}', 'source': 'PO billing instructions / Settings'}],
            }
        if line:
            steps = _line_steps(line, topic)
            if not steps:
                steps = _line_steps(line, None)
                topic = None
            return {
                'answer': f'Here is how {line["name"]} was calculated for {run["period"]} (amount S${line["amount"]:,.2f}). Every figure comes from the rule engine, not from the AI.',
                'steps': steps,
            }
        names = ', '.join(l['name'] for l in run['lines'])
        return {
            'answer': f'Run {run["id"]} covers {names}. Ask about a specific officer (for example "why is {run["lines"][0]["name"] if run["lines"] else "Officer A"} billed this amount?"), about CPF/SDL/fee/GST, or the total.',
            'steps': [],
        }
    if doc:
        i = doc.get('instructions') or {}
        steps = [
            {'n': 1, 'title': 'Billing basis', 'text': str(i.get('billing_basis') or 'not found'), 'source': doc.get('ref')},
            {'n': 2, 'title': 'Management fee', 'text': f'{i["fee_pct"]:g}%' if i.get('fee_pct') is not None else 'not stated', 'source': (i.get('clause_refs') or {}).get('fee_pct') or doc.get('ref')},
            {'n': 3, 'title': 'GST', 'text': f'{i["gst_pct"]:g}%' if i.get('gst_pct') is not None else 'not stated', 'source': (i.get('clause_refs') or {}).get('gst_pct') or doc.get('ref')},
            {'n': 4, 'title': 'Rates', 'text': ', '.join(f'{k}: {v}' for k, v in (i.get('rates') or {}).items() if v) or 'none', 'source': (i.get('clause_refs') or {}).get('rates') or doc.get('ref')},
            {'n': 5, 'title': 'Validity', 'text': f'{i.get("valid_from") or "-"} to {i.get("valid_to") or "-"}', 'source': (i.get('clause_refs') or {}).get('validity') or doc.get('ref')},
        ]
        return {'answer': f'{doc.get("doc_type")} {doc.get("ref")} for {doc.get("party")} (status {doc.get("status")}, confidence {doc.get("confidence")}%). These are the billing instructions extracted from it.', 'steps': steps}
    return {
        'answer': 'Select an invoice run or a document so I can explain it, or ask me to propose a change such as "set OT hours for Officer A to 8". I only explain and propose; the rule engine does the maths and every change needs your confirmation.',
        'steps': [],
    }
