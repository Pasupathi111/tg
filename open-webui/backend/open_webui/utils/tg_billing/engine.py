"""Deterministic, Decimal-based billing engine for TG Billing Coworker.

Pure python (stdlib only) so it can be unit tested standalone.
All money values are rounded to 2 dp with ROUND_HALF_UP and totals are the sum
of the rounded lines.
"""

from __future__ import annotations

import calendar
import copy
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

D = Decimal
TWO = D('0.01')

DEFAULT_SETTINGS: Dict[str, Any] = {
    'company': 'APBA TG Human Resource Pte Ltd',
    'currency': 'SGD',
    'gst_pct': 9,
    'default_fee_pct': 10,
    'cpf': {
        'rate_pct': 17,
        'ow_ceiling': 8000,
        'senior_age': 55,
        'senior_rate_pct': 15.5,
        'apply_to': ['citizen', 'pr'],
    },
    'sdl': {'rate_pct': 0.25, 'min': 2, 'max': 11.25},
    'ot_multiplier': 1.5,
    'ot_hourly_equivalent': {'weeks_per_year': 52, 'hours_per_week': 44},
    'hours_per_day': 8,
}

# fields adjustable on the timesheet / employee (never persisted to the records)
TIMESHEET_FIELDS = [
    'scheduled_days',
    'worked_days',
    'paid_leave_days',
    'unpaid_leave_days',
    'ot_hours',
    'hours',
    'weeks',
    'half_days',
    'deductions',
]
EMPLOYEE_FIELDS = ['monthly_salary', 'hourly_rate', 'weekly_rate', 'half_day_rate', 'daily_rate']
RUN_FIELDS = ['fee_pct']
ADJUSTABLE_FIELDS = TIMESHEET_FIELDS + EMPLOYEE_FIELDS + RUN_FIELDS

BASIS_UNIT = {
    'monthly': 'month',
    'half_day': 'half-day',
    'daily': 'day',
    'weekly': 'week',
    'hourly': 'hour',
}


def dec(v: Any, default: Any = 0) -> Decimal:
    if v is None or v == '':
        return D(str(default))
    if isinstance(v, Decimal):
        return v
    try:
        return D(str(v).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return D(str(default))


def q(v: Any) -> Decimal:
    return dec(v).quantize(TWO, rounding=ROUND_HALF_UP)


def fl(v: Decimal) -> float:
    return float(q(v))


def money(v: Decimal) -> str:
    return f'S${q(v):,.2f}'


def num(v: Decimal) -> str:
    """Compact number for calc strings (no trailing zeros)."""
    s = f'{v.normalize():f}' if v != 0 else '0'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def merge_settings(overrides: Optional[dict]) -> dict:
    out = copy.deepcopy(DEFAULT_SETTINGS)
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def period_bounds(period: str):
    y, m = period.split('-')
    y, m = int(y), int(m)
    last = calendar.monthrange(y, m)[1]
    return f'{y:04d}-{m:02d}-01', f'{y:04d}-{m:02d}-{last:02d}'


def _ts_defaults(ts: Optional[dict]) -> dict:
    return dict(ts or {})


def effective(emp: dict, ts: Optional[dict], overrides: dict, field: str):
    """Current effective value of an adjustable field (override > timesheet/employee)."""
    if field in overrides:
        return overrides[field]
    if field in TIMESHEET_FIELDS:
        return (ts or {}).get(field)
    if field in EMPLOYEE_FIELDS:
        return emp.get(field)
    return None


def cpf_rate(emp: dict, cfg: dict) -> Decimal:
    residency = (emp.get('residency') or 'citizen').lower()
    if residency not in [x.lower() for x in cfg.get('apply_to', ['citizen', 'pr'])]:
        return D(0)
    age = int(dec(emp.get('age'), 30))
    if age <= int(cfg.get('senior_age', 55)):
        return dec(cfg.get('rate_pct', 17))
    return dec(cfg.get('senior_rate_pct', cfg.get('rate_pct', 17)))


def compute_line(
    emp: dict,
    ts: Optional[dict],
    instructions: dict,
    settings: dict,
    overrides: Optional[dict] = None,
    period: str = '',
    ref: str = '',
    fee_pct_override: Optional[Any] = None,
) -> dict:
    """Compute one employee billing line. Returns the Run.lines[] shape."""
    overrides = overrides or {}
    basis = instructions.get('billing_basis') or 'cost_plus'
    pay_basis = (emp.get('pay_basis') or 'monthly').lower()
    ts_src = f'Timesheet {period}' if ts else 'Timesheet (missing)'
    emp_src = 'Employee master'
    doc_src = f'{ref} billing instructions' if ref else 'PO billing instructions'

    def tsv(field, default=0):
        v = effective(emp, ts, overrides, field)
        return dec(v, default) if v is not None else None

    def val(field, default=0):
        v = tsv(field)
        return default if v is None else v

    adjusted_fields = set(overrides.keys())

    def row(label, calc, amount, source, field=None):
        return {
            'label': label,
            'calc': calc,
            'amount': fl(amount),
            'source': source,
            'adjusted': any(f in adjusted_fields for f in ([field] if isinstance(field, str) else (field or []))),
            'field': field if isinstance(field, str) or field is None else field[0],
        }

    sched = D(val('scheduled_days'))
    worked = D(val('worked_days'))
    paid_leave = D(val('paid_leave_days'))
    unpaid = D(val('unpaid_leave_days'))
    paid_days = worked + paid_leave
    ot_hours = D(val('ot_hours'))
    hpd = dec(settings.get('hours_per_day', 8))

    hours = tsv('hours')
    hours = hours if hours is not None else worked * hpd
    weeks = tsv('weeks')
    weeks = weeks if weeks is not None else worked / D(5)
    half_days = tsv('half_days')
    half_days = half_days if half_days is not None else worked * 2

    rates = {
        'monthly': dec(effective(emp, ts, overrides, 'monthly_salary')),
        'hourly': dec(effective(emp, ts, overrides, 'hourly_rate')),
        'weekly': dec(effective(emp, ts, overrides, 'weekly_rate')),
        'half_day': dec(effective(emp, ts, overrides, 'half_day_rate')),
        'daily': dec(effective(emp, ts, overrides, 'daily_rate')),
    }
    rate_field = {
        'monthly': 'monthly_salary',
        'hourly': 'hourly_rate',
        'weekly': 'weekly_rate',
        'half_day': 'half_day_rate',
        'daily': 'daily_rate',
    }[pay_basis]

    sec_a: List[dict] = []
    sec_b: List[dict] = []
    sec_c: List[dict] = []
    sec_d: List[dict] = []
    issues: List[str] = []

    if basis == 'rate_card':
        doc_rates = {k: dec(v) for k, v in (instructions.get('rates') or {}).items() if v not in (None, '')}
        rate = doc_rates.get(pay_basis, D(0))
        if rate <= 0:
            issues.append(f'No {pay_basis} rate in {ref or "document"}')
        label = f'Contract {BASIS_UNIT[pay_basis]} rate'
        if pay_basis == 'monthly':
            if sched > 0 and paid_days < sched:
                amt = q(rate * paid_days / sched)
                calc = f'{money(rate)} x {num(paid_days)}/{num(sched)} days'
            else:
                amt = q(rate)
                calc = f'{money(rate)} x 1 month'
            sec_a.append(row(label, calc, amt, doc_src, ('worked_days', 'paid_leave_days', 'scheduled_days')))
        else:
            units, ufield = {
                'half_day': (half_days, 'half_days'),
                'daily': (paid_days, ('worked_days', 'paid_leave_days')),
                'weekly': (weeks, 'weeks'),
                'hourly': (hours, 'hours'),
            }[pay_basis]
            amt = q(rate * units)
            sec_a.append(
                row(
                    label,
                    f'{num(D(units))} {BASIS_UNIT[pay_basis]}(s) x {money(rate)}',
                    amt,
                    doc_src + ' / ' + ts_src,
                    ufield,
                )
            )
        cost = amt
    else:
        # ---- A. time worked
        if pay_basis == 'monthly':
            daily = rates['monthly'] / sched if sched > 0 else D(0)
            base = q(daily * paid_days)
            sec_a.append(
                row(
                    'Base pay',
                    f'{money(rates["monthly"])} / {num(sched)} days x {num(paid_days)} paid days',
                    base,
                    f'{emp_src} + {ts_src}',
                    ('worked_days', 'paid_leave_days', 'scheduled_days', 'monthly_salary'),
                )
            )
            if unpaid > 0:
                sec_a.append(
                    row(
                        f'Unpaid leave ({num(unpaid)} days)',
                        f'Not billed: excluded from {num(paid_days)} paid days',
                        D(0),
                        ts_src,
                        'unpaid_leave_days',
                    )
                )
            heq = rates['monthly'] * 12 / (
                dec(settings['ot_hourly_equivalent']['weeks_per_year'])
                * dec(settings['ot_hourly_equivalent']['hours_per_week'])
            )
        elif pay_basis == 'hourly':
            base = q(rates['hourly'] * hours)
            sec_a.append(row('Base pay', f'{num(D(hours))} h x {money(rates["hourly"])}', base, f'{emp_src} + {ts_src}', 'hours'))
            heq = rates['hourly']
        elif pay_basis == 'weekly':
            base = q(rates['weekly'] * weeks)
            sec_a.append(row('Base pay', f'{num(D(weeks))} wk x {money(rates["weekly"])}', base, f'{emp_src} + {ts_src}', 'weeks'))
            heq = rates['weekly'] / dec(settings['ot_hourly_equivalent']['hours_per_week'])
        elif pay_basis == 'half_day':
            base = q(rates['half_day'] * half_days)
            sec_a.append(
                row('Base pay', f'{num(D(half_days))} half-days x {money(rates["half_day"])}', base, f'{emp_src} + {ts_src}', 'half_days')
            )
            heq = rates['half_day'] * 2 / hpd
        else:  # daily
            base = q(rates['daily'] * paid_days)
            sec_a.append(row('Base pay', f'{num(paid_days)} days x {money(rates["daily"])}', base, f'{emp_src} + {ts_src}', ('worked_days', 'paid_leave_days', 'daily_rate')))
            heq = rates['daily'] / hpd

        # ---- B. OT, allowances, deductions
        mult = dec(settings.get('ot_multiplier', 1.5))
        if ot_hours > 0:
            ot = q(ot_hours * heq * mult)
            sec_b.append(
                row(
                    'Overtime',
                    f'{num(ot_hours)} h x {money(heq.quantize(D("0.0001")))} x {num(mult)}',
                    ot,
                    f'{ts_src} + Settings (OT multiplier)',
                    'ot_hours',
                )
            )
        for al in emp.get('allowances') or []:
            a = dec(al.get('amount'))
            if a != 0:
                sec_b.append(row(al.get('label') or 'Allowance', 'Fixed allowance', q(a), emp_src))
        ded = dec(val('deductions'))
        if ded != 0:
            sec_b.append(row('Deductions', 'Timesheet deductions', -q(ded), ts_src, 'deductions'))

        gross = sum((dec(r['amount']) for r in sec_a + sec_b), D(0))
        gross = q(gross)

        # ---- C. employer contributions
        cfg = settings['cpf']
        rate = cpf_rate(emp, cfg)
        ceiling = dec(cfg.get('ow_ceiling', 8000))
        if rate > 0:
            ow = min(max(gross, D(0)), ceiling)
            cpf = q(ow * rate / 100)
            sec_c.append(
                row(
                    'Employer CPF',
                    f'{num(rate)}% x min({money(gross)}, ceiling {money(ceiling)})',
                    cpf,
                    'Settings: CPF',
                )
            )
        else:
            sec_c.append(row('Employer CPF', 'Not applicable (non-resident / foreign)', D(0), 'Settings: CPF'))
        sdl_cfg = settings['sdl']
        if gross > 0:
            sdl = dec(sdl_cfg.get('rate_pct', 0.25)) * gross / 100
            sdl = min(max(sdl, dec(sdl_cfg.get('min', 2))), dec(sdl_cfg.get('max', 11.25)))
            sdl = q(sdl)
        else:
            sdl = D(0)
        sec_c.append(
            row(
                'Skills Development Levy',
                f'{num(dec(sdl_cfg.get("rate_pct", 0.25)))}% x {money(gross)} (min {money(dec(sdl_cfg.get("min", 2)))}, max {money(dec(sdl_cfg.get("max", 11.25)))})',
                sdl,
                'Settings: SDL',
            )
        )
        for oc in emp.get('other_contributions') or []:
            a = dec(oc.get('amount'))
            if a != 0:
                sec_c.append(row(oc.get('label') or 'Other contribution', 'From employee record', q(a), emp_src))

        cost = q(sum((dec(r['amount']) for r in sec_a + sec_b + sec_c), D(0)))

    # ---- D. management fee
    if fee_pct_override is not None:
        fee_pct = dec(fee_pct_override)
        fee_src = 'Adjustment'
    elif instructions.get('fee_pct') not in (None, ''):
        fee_pct = dec(instructions.get('fee_pct'))
        fee_src = doc_src
    elif basis == 'cost_plus':
        fee_pct = dec(settings.get('default_fee_pct', 10))
        fee_src = 'Settings: default fee %'
    else:
        fee_pct = D(0)
        fee_src = doc_src
    fee = q(cost * fee_pct / 100) if fee_pct > 0 else D(0)
    if basis == 'cost_plus' or fee_pct > 0:
        fee_row = row('Management fee', f'{num(fee_pct)}% x {money(cost)}', fee, fee_src, 'fee_pct')
        if fee_pct_override is not None:
            fee_row['adjusted'] = True
        sec_d.append(fee_row)

    sections = []
    for key, title, rows in (
        ('A', 'Time worked' if basis == 'cost_plus' else 'Contract amount', sec_a),
        ('B', 'Overtime, allowances & deductions', sec_b),
        ('C', 'Employer contributions', sec_c),
        ('D', 'Management fee', sec_d),
    ):
        if rows:
            sections.append({'key': key, 'title': title, 'rows': rows})

    return {
        'employee_id': emp.get('id'),
        'name': emp.get('name'),
        'pay_basis': pay_basis,
        'sections': sections,
        'cost': fl(cost),
        'fee': fl(fee),
        'amount': fl(cost + fee),
        'issues': issues,
        'timesheet_received': ts is not None,
    }


def build_run(
    doc: dict,
    period: str,
    employees: List[dict],
    timesheets: List[dict],
    settings: dict,
    overrides: Optional[Dict[str, dict]] = None,
) -> dict:
    """Compute a full run (without id / status / adjustments bookkeeping)."""
    settings = merge_settings(settings)
    instr = doc.get('instructions') or {}
    overrides = overrides or {}
    ts_by_emp = {t['employee_id']: t for t in timesheets if t.get('period') == period}
    run_fee = (overrides.get('*') or {}).get('fee_pct')
    basis = instr.get('billing_basis') or 'cost_plus'

    lines = []
    for emp in employees:
        lines.append(
            compute_line(
                emp,
                ts_by_emp.get(emp['id']),
                instr,
                settings,
                overrides.get(emp['id']),
                period=period,
                ref=doc.get('ref', ''),
                fee_pct_override=run_fee,
            )
        )

    subtotal = q(sum((dec(l['amount']) for l in lines), D(0)))
    gst_pct = dec(instr.get('gst_pct')) if instr.get('gst_pct') not in (None, '') else dec(settings.get('gst_pct', 9))
    gst = q(subtotal * gst_pct / 100)
    total = q(subtotal + gst)

    # ---- checks
    checks = []
    start, end = period_bounds(period)
    vf, vt = instr.get('valid_from'), instr.get('valid_to')
    if vt and vt < start:
        checks.append({'label': 'Document valid for period', 'result': 'Fail', 'value': f'Expired {vt}'})
    elif vf and vf > end:
        checks.append({'label': 'Document valid for period', 'result': 'Fail', 'value': f'Starts {vf}'})
    else:
        checks.append({'label': 'Document valid for period', 'result': 'Pass', 'value': f'{vf or "-"} to {vt or "-"}'})
    received = sum(1 for l in lines if l['timesheet_received'])
    checks.append(
        {
            'label': 'Timesheets received',
            'result': 'Pass' if received == len(lines) and lines else 'Fail',
            'value': f'{received}/{len(lines)}',
        }
    )
    if basis == 'rate_card':
        missing = [l['name'] for l in lines if l['issues']]
        checks.append(
            {
                'label': 'Contract rates found',
                'result': 'Fail' if missing else 'Pass',
                'value': ', '.join(missing) if missing else 'All staff rates found',
            }
        )
    else:
        has_fee = instr.get('fee_pct') not in (None, '')
        checks.append(
            {
                'label': 'Management fee from document',
                'result': 'Pass' if has_fee else 'Differs',
                'value': f'{num(dec(instr.get("fee_pct")))}%' if has_fee else 'Not in document, default used',
            }
        )
    doc_gst = instr.get('gst_pct')
    sg = dec(settings.get('gst_pct', 9))
    checks.append(
        {
            'label': 'GST rate',
            'result': 'Match' if doc_gst in (None, '') or dec(doc_gst) == sg else 'Differs',
            'value': f'{num(gst_pct)}%',
        }
    )
    sum_lines = q(sum((dec(l['amount']) for l in lines), D(0)))
    checks.append(
        {
            'label': 'Total equals sum of lines',
            'result': 'Match' if sum_lines == subtotal and q(subtotal + gst) == total else 'Fail',
            'value': money(total),
        }
    )
    if not lines:
        checks.append({'label': 'Staff linked to document', 'result': 'Fail', 'value': 'No staff'})
    refs = instr.get('mandatory_references') or []
    checks.append(
        {
            'label': 'Mandatory references',
            'result': 'Pass' if doc.get('ref') else 'Fail',
            'value': ', '.join([doc.get('ref', '')] + [r for r in refs if r != 'PO number']) .strip(', ') or '-',
        }
    )

    for l in lines:
        l.pop('timesheet_received', None)

    return {
        'document_id': doc.get('id'),
        'period': period,
        'basis': basis,
        'lines': lines,
        'subtotal': fl(subtotal),
        'gst_pct': float(gst_pct),
        'gst': fl(gst),
        'total': fl(total),
        'checks': checks,
    }
