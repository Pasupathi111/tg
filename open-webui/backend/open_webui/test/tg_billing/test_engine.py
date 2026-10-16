from decimal import Decimal

import pytest

from tg_billing_pkg import engine
from tg_billing_pkg.engine import build_run, compute_line, merge_settings, q

S = merge_settings({})
COST_PLUS = {'billing_basis': 'cost_plus', 'fee_pct': 10, 'gst_pct': 9}


def emp(**kw):
    e = {'id': 'E1', 'name': 'Officer X', 'pay_basis': 'monthly', 'age': 30, 'residency': 'citizen',
         'monthly_salary': 0, 'hourly_rate': 0, 'weekly_rate': 0, 'half_day_rate': 0, 'daily_rate': 0,
         'allowances': [], 'other_contributions': []}
    e.update(kw)
    return e


def ts(**kw):
    t = {'employee_id': 'E1', 'period': '2026-09', 'scheduled_days': 22, 'worked_days': 22, 'paid_leave_days': 0,
         'unpaid_leave_days': 0, 'ot_hours': 0, 'deductions': 0}
    t.update(kw)
    return t


def line(e, t, instr=COST_PLUS, **kw):
    return compute_line(e, t, instr, S, period='2026-09', ref='PO-1', **kw)


def rows(l):
    return {r['label']: r for s in l['sections'] for r in s['rows']}


def test_rounding_half_up():
    assert q('1.005') == Decimal('1.01')
    assert q('2.675') == Decimal('2.68')
    assert q('1137.125') == Decimal('1137.13')  # banker's rounding would give .12


def test_monthly_cost_plus_with_unpaid_leave():
    l = line(emp(monthly_salary=4200), ts(worked_days=21, unpaid_leave_days=1))
    r = rows(l)
    assert r['Base pay']['amount'] == 4009.09  # 4200/22*21
    assert r['Employer CPF']['amount'] == 681.55  # 17% of 4009.09
    assert r['Skills Development Levy']['amount'] == 10.02
    assert l['cost'] == 4700.66
    assert l['fee'] == 470.07
    assert l['amount'] == 5170.73


def test_monthly_overtime_uses_52_44_divisor():
    l = line(emp(monthly_salary=4200), ts(worked_days=22, ot_hours=6))
    assert rows(l)['Overtime']['amount'] == 198.25  # 4200*12/(52*44)*6*1.5


def test_cpf_ceiling_and_sdl_max():
    l = line(emp(monthly_salary=10000), ts())
    r = rows(l)
    assert r['Employer CPF']['amount'] == 1360.00  # 17% x 8000 ceiling
    assert r['Skills Development Levy']['amount'] == 11.25
    assert l['cost'] == 11371.25
    assert l['fee'] == 1137.13
    assert l['amount'] == 12508.38


def test_sdl_minimum():
    l = line(emp(pay_basis='hourly', hourly_rate=5), ts(hours=10, worked_days=2))
    r = rows(l)
    assert r['Base pay']['amount'] == 50.0
    assert r['Skills Development Levy']['amount'] == 2.00
    assert r['Employer CPF']['amount'] == 8.50


def test_hourly_basis_with_ot():
    l = line(emp(pay_basis='hourly', hourly_rate=22.5, residency='pr'), ts(hours=176, ot_hours=5))
    r = rows(l)
    assert r['Base pay']['amount'] == 3960.0
    assert r['Overtime']['amount'] == 168.75
    assert r['Employer CPF']['amount'] == 701.89
    assert r['Skills Development Levy']['amount'] == 10.32
    assert l['cost'] == 4840.96 and l['fee'] == 484.10 and l['amount'] == 5325.06


def test_weekly_foreign_no_cpf_levy_and_sdl_cap():
    e = emp(pay_basis='weekly', weekly_rate=1100, age=41, residency='foreign',
            other_contributions=[{'label': 'Foreign worker levy', 'amount': 300}])
    l = line(e, ts(weeks=4.4, ot_hours=10))
    r = rows(l)
    assert r['Base pay']['amount'] == 4840.0
    assert r['Overtime']['amount'] == 375.0  # 1100/44 * 1.5 * 10
    assert r['Employer CPF']['amount'] == 0
    assert r['Skills Development Levy']['amount'] == 11.25
    assert r['Foreign worker levy']['amount'] == 300
    assert l['cost'] == 5526.25 and l['fee'] == 552.63 and l['amount'] == 6078.88


def test_half_day_basis():
    l = line(emp(pay_basis='half_day', half_day_rate=90), ts(half_days=30))
    assert rows(l)['Base pay']['amount'] == 2700.0
    assert l['cost'] == 3165.75 and l['fee'] == 316.58 and l['amount'] == 3482.33


def test_senior_cpf_rate():
    l = line(emp(monthly_salary=4000, age=58), ts())
    assert rows(l)['Employer CPF']['amount'] == 620.0  # 15.5%


def test_allowance_and_deduction():
    e = emp(monthly_salary=4000, allowances=[{'label': 'Transport', 'amount': 150}])
    l = line(e, ts(deductions=50))
    r = rows(l)
    assert r['Transport']['amount'] == 150
    assert r['Deductions']['amount'] == -50
    assert r['Employer CPF']['amount'] == 697.0  # 17% x (4000 + 150 - 50)


RC = {'billing_basis': 'rate_card', 'fee_pct': None, 'gst_pct': 9,
      'rates': {'monthly': 5200, 'half_day': 180, 'daily': 340, 'weekly': 1500, 'hourly': 45}}


def test_rate_card_monthly_full_and_prorated():
    full = line(emp(), ts(), RC)
    assert full['cost'] == 5200.0 and full['fee'] == 0 and full['amount'] == 5200.0
    pr = line(emp(), ts(worked_days=21), RC)
    assert pr['amount'] == 4963.64  # 5200 x 21/22


def test_rate_card_other_units():
    assert line(emp(pay_basis='half_day'), ts(half_days=28), RC)['amount'] == 5040.0
    assert line(emp(pay_basis='hourly'), ts(hours=10.5), RC)['amount'] == 472.5
    assert line(emp(pay_basis='daily'), ts(worked_days=20, paid_leave_days=1), RC)['amount'] == 7140.0
    assert line(emp(pay_basis='weekly'), ts(weeks=4), RC)['amount'] == 6000.0


def test_rate_card_missing_rate_flagged():
    d = dict(RC, rates={'monthly': None})
    l = line(emp(pay_basis='hourly'), ts(hours=5), d)
    assert l['amount'] == 0 and l['issues']


def test_rate_card_fee_when_document_says():
    d = dict(RC, fee_pct=5)
    l = line(emp(), ts(), d)
    assert l['fee'] == 260.0 and l['amount'] == 5460.0


def test_run_totals_gst():
    doc = {'id': 'D1', 'ref': 'PO-1', 'instructions': COST_PLUS}
    e1 = emp(id='E1', monthly_salary=4200)
    e2 = emp(id='E2', pay_basis='hourly', hourly_rate=22.5, residency='pr')
    t = [ts(employee_id='E1', worked_days=21, unpaid_leave_days=1),
         ts(employee_id='E2', hours=176, ot_hours=5)]
    run = build_run(doc, '2026-09', [e1, e2], t, {})
    assert [l['amount'] for l in run['lines']] == [5170.73, 5325.06]
    assert run['subtotal'] == 10495.79
    assert run['gst'] == 944.62  # 9% half-up of 944.6211
    assert run['total'] == 11440.41
    assert run['subtotal'] == round(sum(l['amount'] for l in run['lines']), 2)
    labels = {c['label']: c['result'] for c in run['checks']}
    assert labels['Timesheets received'] == 'Pass' and labels['Document valid for period'] == 'Pass'


def test_run_checks_missing_timesheet_and_expiry():
    doc = {'id': 'D1', 'ref': 'PO-1', 'instructions': dict(COST_PLUS, valid_to='2025-12-31')}
    run = build_run(doc, '2026-09', [emp(monthly_salary=4000)], [], {})
    labels = {c['label']: c['result'] for c in run['checks']}
    assert labels['Timesheets received'] == 'Fail'
    assert labels['Document valid for period'] == 'Fail'


def test_override_marks_adjusted_and_recalculates():
    doc = {'id': 'D1', 'ref': 'PO-1', 'instructions': COST_PLUS}
    e = emp(monthly_salary=4200)
    base = build_run(doc, '2026-09', [e], [ts(ot_hours=0)], {})
    adj = build_run(doc, '2026-09', [e], [ts(ot_hours=0)], {}, {'E1': {'ot_hours': 8}})
    assert adj['total'] > base['total']
    ot = [r for s in adj['lines'][0]['sections'] for r in s['rows'] if r['label'] == 'Overtime'][0]
    assert ot['adjusted'] is True


def test_fee_override_run_level():
    doc = {'id': 'D1', 'ref': 'PO-1', 'instructions': COST_PLUS}
    run = build_run(doc, '2026-09', [emp(monthly_salary=4000)], [ts()], {}, {'*': {'fee_pct': 12}})
    fee_row = [r for s in run['lines'][0]['sections'] for r in s['rows'] if r['label'] == 'Management fee'][0]
    assert fee_row['adjusted'] and fee_row['calc'].startswith('12%')
